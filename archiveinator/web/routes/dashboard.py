"""Dashboard route: the main landing page after login."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.models import ArchiveJob
from archiveinator.web.templates import esc_html, render_page

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> HTMLResponse:
    recent = (
        db.query(ArchiveJob)
        .filter(ArchiveJob.user_id == user.id)
        .order_by(ArchiveJob.created_at.desc())
        .limit(5)
        .all()
    )

    total = db.query(ArchiveJob).filter(ArchiveJob.user_id == user.id).count()
    success_count = (
        db.query(ArchiveJob)
        .filter(ArchiveJob.user_id == user.id, ArchiveJob.status == "completed")
        .count()
    )

    jobs_html = ""
    for j in recent:
        badge_class = {
            "completed": "badge-success",
            "failed": "badge-failed",
            "pending": "badge-pending",
            "running": "badge-running",
        }.get(j.status, "badge-pending")
        jobs_html += f"""<li>
  <span class="badge {badge_class}">{j.status}</span>
  <span class="job-url">{esc_html(j.title or j.url)}</span>
  <small style="color:var(--text-muted)">{j.created_at.strftime("%Y-%m-%d %H:%M") if j.created_at else ""}</small>
</li>"""

    body = f"""<div class="hero">
  <h1>Archive a Page</h1>
  <p>Enter a URL to create a self-contained, ad-free, paywall-bypassed archive</p>

  <form class="archive-form" id="archive-form" method="post" action="/archive">
    <input type="url" name="url" placeholder="https://example.com/article" required autofocus>
    <button type="submit" class="btn btn-primary">Archive</button>
  </form>

  <div class="profile-indicator" id="profile-indicator"></div>

  <div class="progress-area" id="progress-area" style="display:none">
    <div class="progress-bar"><div class="progress-bar-fill" id="progress-fill"></div></div>
    <div class="progress-messages" id="progress-messages"></div>
  </div>

  <div id="result-area"></div>
</div>

<div class="stats">
  <div class="stat-card">
    <div class="stat-value">{total}</div>
    <div class="stat-label">Total Archives</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{success_count}</div>
    <div class="stat-label">Successful</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{total - success_count}</div>
    <div class="stat-label">Failed</div>
  </div>
</div>

<div class="card">
  <h2>Recent Archives</h2>
  {"<ul class='job-list'>" + jobs_html + "</ul>" if jobs_html else '<p class="empty-state">No archives yet. Enter a URL above to get started.</p>'}
</div>

<script src="/static/js/archive.js"></script>"""

    return HTMLResponse(render_page("Dashboard", body, request))
