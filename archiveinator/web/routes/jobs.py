"""Job history: paginated, filterable list of past archive jobs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.models import ArchiveJob
from archiveinator.web.templates import esc_html, render_page

router = APIRouter(tags=["jobs"])


def _badge_html(status: str) -> str:
    cls = {
        "completed": "badge-success",
        "failed": "badge-failed",
        "pending": "badge-pending",
        "running": "badge-running",
    }.get(status, "badge-pending")
    return f'<span class="badge {cls}">{status}</span>'


_PER_PAGE = 25


@router.get("/jobs")
async def job_history(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    status: str | None = None,
    domain: str | None = None,
    page: int = 1,
) -> Response:
    """Show paginated job history with optional filters."""
    query = db.query(ArchiveJob).filter(ArchiveJob.user_id == user.id)

    if status:
        query = query.filter(ArchiveJob.status == status)
    if domain:
        query = query.filter(ArchiveJob.url.like(f"%://{domain}%"))

    total = query.count()
    total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)
    page = max(1, min(page, total_pages))

    jobs = (
        query.order_by(ArchiveJob.created_at.desc())
        .offset((page - 1) * _PER_PAGE)
        .limit(_PER_PAGE)
        .all()
    )

    rows = ""
    for j in jobs:
        ts = j.created_at.strftime("%Y-%m-%d %H:%M") if j.created_at else ""
        paywall_info = ""
        if j.paywalled:
            paywall_info = '<span class="paywall-badge">Paywall</span>'
            if j.bypass_method:
                paywall_info += f" bypass: {j.bypass_method}"
        elif j.paywalled is False and j.status == "completed":
            paywall_info = '<span class="paywall-badge paywall-ok">Open</span>'

        rows += f"""<tr>
  <td class="cell-ts">{ts}</td>
  <td class="cell-url"><a href="/download/{j.id}?view=1">{esc_html(j.title or j.url[:80])}</a></td>
  <td>{_badge_html(j.status)}</td>
  <td class="cell-meta">{paywall_info}</td>
  <td class="cell-meta">{j.duration_seconds or "—"}s</td>
  <td class="cell-actions">
    <a href="/download/{j.id}" class="btn btn-sm">Download</a>
    <a href="/download/{j.id}?view=1" class="btn btn-sm">View</a>
  </td>
</tr>"""

    if not rows:
        table = '<p class="empty-state">No archive jobs yet. <a href="/dashboard">Archive a URL</a> to get started.</p>'
    else:
        table = f"""<table class="job-table">
<thead><tr>
  <th>Date</th>
  <th>URL / Title</th>
  <th>Status</th>
  <th>Access</th>
  <th>Duration</th>
  <th>Actions</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""

    # Pagination links
    pagination = ""
    if total_pages > 1:
        pagination = '<div class="pagination">'
        if page > 1:
            pagination += f'<a href="/jobs?page={page - 1}" class="btn btn-sm">Previous</a>'
        pagination += f'<span class="page-info">Page {page} of {total_pages}</span>'
        if page < total_pages:
            pagination += f'<a href="/jobs?page={page + 1}" class="btn btn-sm">Next</a>'
        pagination += "</div>"

    # Filter form
    filter_form = f"""<form class="filter-form" method="get" action="/jobs">
  <select name="status">
    <option value="">All statuses</option>
    <option value="completed" {"selected" if status == "completed" else ""}>Completed</option>
    <option value="failed" {"selected" if status == "failed" else ""}>Failed</option>
    <option value="running" {"selected" if status == "running" else ""}>Running</option>
    <option value="pending" {"selected" if status == "pending" else ""}>Pending</option>
  </select>
  <input type="text" name="domain" placeholder="Filter by domain" value="{domain or ""}">
  <button type="submit" class="btn btn-sm">Filter</button>
  <a href="/jobs" class="btn btn-sm">Clear</a>
</form>"""

    body = f"""<div class="card">
  <div class="card-header">
    <h2>Archive History</h2>
    <span class="total-count">{total} total</span>
  </div>
  {filter_form}
  {table}
  {pagination}
</div>"""

    return HTMLResponse(render_page("Archive History", body, request))
