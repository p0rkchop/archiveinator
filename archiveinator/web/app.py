"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from archiveinator.web.models import create_all

_APP: FastAPI | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> None:  # noqa: ARG001
    create_all()
    yield


def create_app() -> FastAPI:
    global _APP
    if _APP is not None:
        return _APP

    app = FastAPI(title="archiveinator", version="0.9.0", lifespan=_lifespan)

    # Mount static files
    import importlib.resources

    static_dir = importlib.resources.files("archiveinator.web") / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Root redirect to dashboard
    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=302)

    _APP = app
    return app
