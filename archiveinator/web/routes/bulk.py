"""Bulk URL import: upload bookmark files, plain text, or CSV for batch archiving."""

from __future__ import annotations

import csv
import io
import re
import time
from typing import Any

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.job_manager import get_job_manager
from archiveinator.web.models import ArchiveJob
from archiveinator.web.templates import esc_html, render_page

router = APIRouter(tags=["bulk"])

# In-memory bulk import tracking
# bulk_id -> dict of import state
_bulk_imports: dict[int, dict[str, Any]] = {}
_next_bulk_id = 1
_MAX_CONCURRENT = 5


@router.get("/bulk")
async def bulk_page(
    request: Request,
    user: Any = Depends(get_current_user),
) -> Response:
    """Show the bulk import page."""
    body = """<div class="card">
  <h2>Bulk URL Import</h2>
  <p class="help-text">Upload a file containing multiple URLs to archive them all at once.</p>

  <form method="post" action="/bulk" enctype="multipart/form-data" class="bulk-form">
    <div class="form-group">
      <label for="file">File</label>
      <div class="file-drop-zone" id="bulk-drop-zone">
        <p>Drag & drop a file here, or click to browse</p>
        <input type="file" id="file" name="file" class="file-input"
               accept=".html,.htm,.txt,.csv,.json">
      </div>
    </div>
    <div class="form-group">
      <label>Format</label>
      <div class="format-info">
        <p><strong>Supported formats:</strong></p>
        <ul>
          <li><strong>Netscape bookmarks HTML</strong> — exported from any browser</li>
          <li><strong>Plain text</strong> — one URL per line, # for comments</li>
          <li><strong>CSV</strong> — must have a <code>url</code> column, optional <code>schedule</code> and <code>profile</code></li>
        </ul>
      </div>
    </div>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Import & Archive</button>
      <a href="/dashboard" class="btn">Cancel</a>
    </div>
  </form>
</div>

<div id="bulk-results"></div>

<script>
(function() {
  var dropZone = document.getElementById('bulk-drop-zone');
  var fileInput = document.getElementById('file');
  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('dragover', function(e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', function() {
    dropZone.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
    }
  });
  dropZone.addEventListener('click', function() { fileInput.click(); });
  fileInput.addEventListener('change', function() {
    if (fileInput.files.length > 0) {
      dropZone.querySelector('p').textContent = fileInput.files[0].name;
    }
  });
})();
</script>"""

    return HTMLResponse(render_page("Bulk Import", body, request))


_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _extract_urls_from_html(html: str) -> list[str]:
    """Extract URLs from a Netscape-format bookmarks HTML file."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        url = a_tag["href"].strip()
        if url.startswith(("http://", "https://")):
            urls.append(url)
    return urls


def _extract_urls_from_text(text: str) -> list[str]:
    """Extract URLs from plain text (one per line, # comments)."""
    urls: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("http://", "https://")):
            urls.append(line)
        else:
            # Try to find URLs anywhere in the line
            for match in _URL_RE.finditer(line):
                urls.append(match.group(0))
    return urls


def _extract_urls_from_csv(text: str) -> list[dict[str, str]]:
    """Extract URLs with optional metadata from CSV."""
    reader = csv.DictReader(io.StringIO(text))
    entries: list[dict[str, str]] = []
    for row in reader:
        url = (row.get("url") or "").strip()
        if url and url.startswith(("http://", "https://")):
            entry: dict[str, str] = {"url": url}
            if row.get("schedule"):
                entry["schedule"] = row["schedule"].strip()
            if row.get("profile"):
                entry["profile"] = row["profile"].strip()
            entries.append(entry)
    return entries


def _detect_format(content: str, filename: str) -> str:
    """Detect the format of uploaded content."""
    lower_name = filename.lower()
    if lower_name.endswith((".html", ".htm")):
        return "html"
    if lower_name.endswith(".csv"):
        return "csv"
    return "text"


@router.post("/bulk")
async def bulk_import(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    file: UploadFile | None = None,
) -> Response:
    """Handle bulk file upload and queue archive jobs."""
    global _next_bulk_id

    if file is None or not file.filename:
        return HTMLResponse(
            render_page(
                "Bulk Import",
                '<div class="card"><p class="error-message">No file uploaded.</p><a href="/bulk" class="btn">Try again</a></div>',
                request,
            ),
        )

    content = (await file.read()).decode("utf-8", errors="replace")
    fmt = _detect_format(content, file.filename)

    # Extract URLs
    raw_entries: list[dict[str, str]] = []
    if fmt == "html":
        for url in _extract_urls_from_html(content):
            raw_entries.append({"url": url})
    elif fmt == "csv":
        raw_entries = _extract_urls_from_csv(content)
    else:
        for url in _extract_urls_from_text(content):
            raw_entries.append({"url": url})

    if not raw_entries:
        return HTMLResponse(
            render_page(
                "Bulk Import",
                '<div class="card"><p class="error-message">No valid URLs found in the uploaded file.</p><a href="/bulk" class="btn">Try again</a></div>',
                request,
            ),
        )

    # Deduplicate URLs from this import
    seen: set[str] = set()
    entries: list[dict[str, str]] = []
    for entry in raw_entries:
        url = entry["url"].rstrip("/")
        if url not in seen:
            seen.add(url)
            entries.append(
                {
                    "url": url,
                    "schedule": entry.get("schedule", ""),
                    "profile": entry.get("profile", ""),
                }
            )

    # Create bulk import record
    bulk_id = _next_bulk_id
    _next_bulk_id += 1

    bulk_state: dict[str, Any] = {
        "id": bulk_id,
        "user_id": user.id,
        "total": len(entries),
        "queued": 0,
        "completed": 0,
        "failed": 0,
        "urls": [
            {"url": e["url"], "status": "pending", "job_id": None, "error": None} for e in entries
        ],
        "created_at": time.time(),
    }
    _bulk_imports[bulk_id] = bulk_state

    # Create DB records and submit jobs
    jm = get_job_manager()

    for idx, entry in enumerate(entries):
        url = entry["url"]
        job = ArchiveJob(
            user_id=user.id,
            url=url,
            status="pending",
        )
        db.add(job)
        db.flush()

        bulk_state["urls"][idx]["job_id"] = job.id
        bulk_state["urls"][idx]["status"] = "queued"
        bulk_state["queued"] += 1

        # Submit to job manager (rate-limited internally)
        await jm.submit(user.id, url)
        # Simplified tracking — just mark as submitted
        bulk_state["urls"][idx]["status"] = "running"

    return RedirectResponse(url=f"/bulk/{bulk_id}", status_code=302)


@router.get("/bulk/{bulk_id}")
async def bulk_status(
    request: Request,
    bulk_id: int,
    user: Any = Depends(get_current_user),
) -> Response:
    """Show the status of a bulk import."""
    bulk = _bulk_imports.get(bulk_id)
    if bulk is None or bulk["user_id"] != user.id:
        return HTMLResponse(
            render_page("Not Found", "<p>Bulk import not found.</p>", request),
            status_code=404,
        )

    # Count current statuses
    completed = sum(1 for u in bulk["urls"] if u["status"] == "completed")
    failed = sum(1 for u in bulk["urls"] if u["status"] == "failed")
    running = sum(1 for u in bulk["urls"] if u["status"] == "running")
    pending = sum(1 for u in bulk["urls"] if u["status"] in ("pending", "queued"))
    total = bulk["total"]

    rows = ""
    for u in bulk["urls"][:100]:  # Show first 100
        badge_cls = {
            "completed": "badge-success",
            "failed": "badge-failed",
            "running": "badge-running",
            "queued": "badge-pending",
            "pending": "badge-pending",
        }.get(u["status"], "badge-pending")

        actions = ""
        if u["job_id"] and u["status"] == "completed":
            actions = f'<a href="/download/{u["job_id"]}" class="btn btn-sm">View</a>'

        rows += f"""<tr>
  <td class="cell-url">{esc_html(u["url"][:80])}</td>
  <td><span class="badge {badge_cls}">{u["status"]}</span></td>
  <td class="cell-meta">{u.get("error", "")[:50] or ""}</td>
  <td>{actions}</td>
</tr>"""

    progress_pct = ((completed + failed) / total * 100) if total else 0

    body = f"""<div class="card">
  <div class="card-header">
    <h2>Bulk Import #{bulk_id}</h2>
    <a href="/bulk" class="btn">New Import</a>
  </div>

  <div class="stats">
    <div class="stat-card">
      <div class="stat-value">{total}</div>
      <div class="stat-label">Total URLs</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{completed}</div>
      <div class="stat-label">Completed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{failed}</div>
      <div class="stat-label">Failed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{running + pending}</div>
      <div class="stat-label">In Progress</div>
    </div>
  </div>

  <div class="progress-bar" style="margin: 1rem 0;">
    <div class="progress-bar-fill" style="width: {progress_pct}%;"></div>
  </div>

  <h3>URLs</h3>
  <table>
    <thead><tr>
      <th>URL</th>
      <th>Status</th>
      <th>Error</th>
      <th>Archive</th>
    </tr></thead>
    <tbody>{(rows if rows else '<tr><td colspan="4" class="empty-state">No URLs.</td></tr>')}</tbody>
  </table>
</div>

<script>
// Auto-refresh if still in progress
if ({running + pending} > 0) {{
  setTimeout(function() {{ location.reload(); }}, 5000);
}}
</script>"""

    return HTMLResponse(render_page("Bulk Import", body, request))
