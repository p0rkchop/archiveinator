"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from archiveinator.web.models import create_all

_APP: FastAPI | None = None

_SECRET_KEY: str | None = None


def get_secret_key() -> str:
    """Return a stable secret key for session signing.

    Uses a file-based key stored alongside the SQLite DB so sessions
    survive container restarts with a persistent /data volume mount.
    """
    global _SECRET_KEY
    if _SECRET_KEY is not None:
        return _SECRET_KEY

    from archiveinator.web.db import db_path

    key_file = db_path().parent / ".session_key"
    if key_file.exists():
        _SECRET_KEY = key_file.read_text().strip()
    else:
        import secrets

        _SECRET_KEY = secrets.token_hex(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(_SECRET_KEY)
    return _SECRET_KEY


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    create_all()
    # Restore scheduled archive jobs
    from archiveinator.web.scheduler import restore_schedules, start_scheduler

    restore_schedules()
    start_scheduler()
    yield
    # Shut down scheduler on server stop
    from archiveinator.web.scheduler import shutdown_scheduler

    shutdown_scheduler()


def create_app() -> FastAPI:
    global _APP
    if _APP is not None:
        return _APP

    app = FastAPI(title="archiveinator", version="0.9.5", lifespan=_lifespan)

    # Session middleware (signs cookies with stable key)
    app.add_middleware(SessionMiddleware, secret_key=get_secret_key())

    # Mount static files
    import importlib.resources

    static_dir = importlib.resources.files("archiveinator.web") / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routers
    from archiveinator.web.routes.archive import router as archive_router
    from archiveinator.web.routes.auth import router as auth_router
    from archiveinator.web.routes.bulk import router as bulk_router
    from archiveinator.web.routes.config import router as config_router
    from archiveinator.web.routes.dashboard import router as dashboard_router
    from archiveinator.web.routes.feeds import router as feeds_router
    from archiveinator.web.routes.jobs import router as jobs_router
    from archiveinator.web.routes.profiles import router as profiles_router
    from archiveinator.web.routes.schedules import router as schedules_router

    app.include_router(archive_router)
    app.include_router(auth_router)
    app.include_router(bulk_router)
    app.include_router(config_router)
    app.include_router(dashboard_router)
    app.include_router(feeds_router)
    app.include_router(jobs_router)
    app.include_router(profiles_router)
    app.include_router(schedules_router)

    # Redirect 401 responses to login page for browser requests (HTML-accepting)
    @app.exception_handler(HTTPException)
    async def _auth_exception_handler(
        req: Request, exc: HTTPException
    ) -> RedirectResponse | JSONResponse:
        if exc.status_code == http_status.HTTP_401_UNAUTHORIZED:
            accept = req.headers.get("accept", "")
            if "text/html" in accept and "/auth/" not in req.url.path:
                return RedirectResponse(url="/auth/login?next=" + req.url.path, status_code=302)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail or ""})

    # Root redirect to dashboard
    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=302)

    _APP = app
    return app
