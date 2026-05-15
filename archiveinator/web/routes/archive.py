"""Archive job submission, WebSocket progress streaming, and file download routes."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from archiveinator.config import data_dir as _data_dir
from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.job_manager import get_job_manager
from archiveinator.web.models import ArchiveJob

router = APIRouter(tags=["archive"])


@router.post("/archive")
async def submit_archive(
    request: Request,
    url: str = Form(...),
    db: Any = Depends(get_session),
    user: Any = Depends(get_current_user),
) -> JSONResponse:
    """Submit a URL for archiving. Returns JSON with job_id."""
    # Validate URL
    if not url.startswith(("http://", "https://")):
        return JSONResponse(
            status_code=400, content={"error": "URL must start with http:// or https://"}
        )

    domain = url.split("/")[2] if "://" in url else ""

    # Check for matching site profile
    from archiveinator.web.models import SiteProfile

    profile = (
        db.query(SiteProfile)
        .filter(
            SiteProfile.user_id == user.id,
            SiteProfile.domain == domain,
        )
        .first()
    )

    # Create DB record
    job = ArchiveJob(
        user_id=user.id,
        url=url,
        status="pending",
        site_profile_id=profile.id if profile else None,
        site_profile_label=profile.label if profile else None,
    )
    db.add(job)
    db.flush()
    job_id = job.id

    # Submit to job manager
    jm = get_job_manager()
    await jm.submit(user.id, url, profile_id=profile.id if profile else None)

    return JSONResponse({"job_id": job_id})


@router.get("/archive/{job_id}")
async def get_job(
    job_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> JSONResponse:
    """Get job details as JSON."""
    job = (
        db.query(ArchiveJob).filter(ArchiveJob.id == job_id, ArchiveJob.user_id == user.id).first()
    )
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    return JSONResponse(
        {
            "id": job.id,
            "url": job.url,
            "status": job.status,
            "title": job.title,
            "final_url": job.final_url,
            "response_status": job.response_status,
            "word_count": job.word_count,
            "paywalled": job.paywalled,
            "paywall_reason": job.paywall_reason,
            "bypass_method": job.bypass_method,
            "is_partial": job.is_partial,
            "error": job.error,
            "output_file": job.output_file,
            "duration_seconds": job.duration_seconds,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    )


@router.websocket("/archive/{job_id}/ws")
async def archive_websocket(websocket: WebSocket, job_id: int) -> None:
    """WebSocket endpoint for real-time archive progress."""
    await websocket.accept()
    jm = get_job_manager()
    q = await jm.get_queue(job_id)
    if q is None:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close()
        return

    try:
        while True:
            msg = await q.get()
            await websocket.send_json(msg)
            if msg.get("type") in ("complete", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        with suppress(Exception):
            await websocket.close()


@router.get("/download/{job_id}")
async def download_file(
    job_id: int,
    view: int = 0,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Download or view an archived HTML file."""
    job = (
        db.query(ArchiveJob).filter(ArchiveJob.id == job_id, ArchiveJob.user_id == user.id).first()
    )
    if not job or not job.output_file:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    file_path = _data_dir() / job.output_file
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "File not found on disk"})

    if view:
        return HTMLResponse(content=file_path.read_text(encoding="utf-8"))
    else:
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'},
        )
