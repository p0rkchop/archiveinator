"""Site profile CRUD routes: manage per-domain cookie profiles."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.models import SiteProfile
from archiveinator.web.templates import render_page

router = APIRouter(tags=["profiles"])


@router.get("/profiles")
async def profile_list(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """List all site profiles for the current user."""
    profiles = (
        db.query(SiteProfile)
        .filter(SiteProfile.user_id == user.id)
        .order_by(SiteProfile.domain)
        .all()
    )

    rows = ""
    for p in profiles:
        cookie_count = len(json.loads(p.cookies_json)) if p.cookies_json else 0
        rows += f"""<tr>
  <td><a href="/profiles/{p.id}/edit">{p.domain}</a></td>
  <td>{p.label or ""}</td>
  <td>{cookie_count}</td>
  <td>{"✓" if p.use_stealth else ""}</td>
  <td>{p.ua_override or "—"}</td>
  <td>{p.timeout_seconds or "—"}s</td>
  <td class="actions">
    <a href="/profiles/{p.id}/edit" class="btn btn-sm">Edit</a>
    <form method="post" action="/profiles/{p.id}/delete" style="display:inline"
          onsubmit="return confirm('Delete profile for {p.domain}?')">
      <button type="submit" class="btn btn-sm btn-danger">Delete</button>
    </form>
  </td>
</tr>"""

    if rows:
        table = f"""<table class="profile-table">
<thead><tr>
  <th>Domain</th>
  <th>Label</th>
  <th>Cookies</th>
  <th>Stealth</th>
  <th>UA</th>
  <th>Timeout</th>
  <th>Actions</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""
    else:
        table = '<p class="empty-state">No site profiles yet. <a href="/profiles/new">Create one</a>.</p>'

    body = f"""<div class="card">
  <div class="card-header">
    <h2>Site Profiles</h2>
    <a href="/profiles/new" class="btn btn-primary">New Profile</a>
  </div>
  {table}
</div>"""

    return HTMLResponse(render_page("Profiles", body, request))


@router.get("/profiles/new")
async def profile_new_form(
    request: Request,
    user: Any = Depends(get_current_user),
) -> Response:
    """Show the create profile form."""
    body = """<div class="card">
  <h2>New Site Profile</h2>
  <form method="post" action="/profiles" class="profile-form" id="profile-form">
    <div class="form-group">
      <label for="domain">Domain</label>
      <input type="text" id="domain" name="domain" required
             placeholder="example.com">
    </div>
    <div class="form-group">
      <label for="label">Label (optional)</label>
      <input type="text" id="label" name="label"
             placeholder="My Newspaper">
    </div>
    <div class="form-group">
      <label for="cookies_file">Cookies File (JSON)</label>
      <div class="file-drop-zone" id="file-drop-zone">
        <p>Drag & drop a cookies JSON file here, or click to browse</p>
        <input type="file" id="cookies_file" name="cookies_file"
               accept=".json" class="file-input">
        <input type="hidden" name="cookies_json" id="cookies_json" value="">
      </div>
      <div id="cookie-preview" class="cookie-preview" style="display:none">
        <p><strong id="cookie-count">0</strong> cookies loaded from <span id="cookie-source"></span></p>
      </div>
      <small class="help-text">Supports Cookie-Editor, EditThisCookie, and Playwright storage state formats.</small>
    </div>
    <fieldset>
      <legend>Advanced Settings</legend>
      <div class="form-group">
        <label for="ua_override">User-Agent Override</label>
        <input type="text" id="ua_override" name="ua_override"
               placeholder="Mozilla/5.0 ...">
      </div>
      <div class="form-group">
        <label for="timeout_seconds">Timeout (seconds)</label>
        <input type="number" id="timeout_seconds" name="timeout_seconds"
               min="5" max="300" placeholder="Default">
      </div>
      <div class="form-group checkbox-group">
        <label>
          <input type="checkbox" name="use_stealth" value="1">
          Enable stealth browser (anti-fingerprinting)
        </label>
      </div>
    </fieldset>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Create Profile</button>
      <a href="/profiles" class="btn">Cancel</a>
    </div>
  </form>
</div>

<script src="/static/js/profiles.js"></script>"""

    return HTMLResponse(render_page("New Profile", body, request))


@router.post("/profiles")
async def profile_create(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    domain: str = Form(...),
    label: str | None = Form(default=None),
    cookies_json: str | None = Form(default=None),
    ua_override: str | None = Form(default=None),
    timeout_seconds: int | None = Form(default=None),
    use_stealth: bool = Form(default=False),
) -> Response:
    """Create a new site profile."""
    # Validate domain
    domain = domain.strip().lower()
    if not domain:
        return JSONResponse(status_code=400, content={"error": "Domain is required"})

    # Check for duplicate
    existing = (
        db.query(SiteProfile)
        .filter(SiteProfile.user_id == user.id, SiteProfile.domain == domain)
        .first()
    )
    if existing:
        return _profile_error("A profile for this domain already exists.", request)

    profile = SiteProfile(
        user_id=user.id,
        domain=domain,
        label=label or None,
        cookies_json=cookies_json or None,
        ua_override=ua_override or None,
        timeout_seconds=timeout_seconds,
        use_stealth=use_stealth,
    )
    db.add(profile)

    return RedirectResponse(url="/profiles", status_code=302)


@router.get("/profiles/{profile_id}/edit")
async def profile_edit_form(
    request: Request,
    profile_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Show the edit profile form."""
    profile = (
        db.query(SiteProfile)
        .filter(SiteProfile.id == profile_id, SiteProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return HTMLResponse(
            render_page("Not Found", "<p>Profile not found.</p>", request),
            status_code=404,
        )

    cookie_count = len(json.loads(profile.cookies_json)) if profile.cookies_json else 0
    cookie_preview = ""
    if profile.cookies_json:
        cookie_preview = f"""<div class="cookie-preview">
  <p><strong>{cookie_count}</strong> cookies stored</p>
</div>"""

    body = f"""<div class="card">
  <h2>Edit Profile: {profile.domain}</h2>
  <form method="post" action="/profiles/{profile.id}/edit" class="profile-form">
    <div class="form-group">
      <label for="label">Label</label>
      <input type="text" id="label" name="label" value="{profile.label or ""}">
    </div>
    <div class="form-group">
      <label for="cookies_file">Replace Cookies (JSON)</label>
      <div class="file-drop-zone" id="file-drop-zone">
        <p>Drag & drop a new cookies file, or click to browse</p>
        <input type="file" id="cookies_file" name="cookies_file"
               accept=".json" class="file-input">
      </div>
      {cookie_preview}
      <label class="checkbox-group" style="margin-top: 8px">
        <input type="checkbox" name="clear_cookies" value="1">
        Remove stored cookies
      </label>
    </div>
    <fieldset>
      <legend>Advanced Settings</legend>
      <div class="form-group">
        <label for="ua_override">User-Agent Override</label>
        <input type="text" id="ua_override" name="ua_override"
               value="{profile.ua_override or ""}">
      </div>
      <div class="form-group">
        <label for="timeout_seconds">Timeout (seconds)</label>
        <input type="number" id="timeout_seconds" name="timeout_seconds"
               min="5" max="300" value="{profile.timeout_seconds or ""}">
      </div>
      <div class="form-group checkbox-group">
        <label>
          <input type="checkbox" name="use_stealth" value="1"
                 {"checked" if profile.use_stealth else ""}>
          Enable stealth browser (anti-fingerprinting)
        </label>
      </div>
    </fieldset>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Save Changes</button>
      <a href="/profiles" class="btn">Cancel</a>
    </div>
  </form>
</div>

<script src="/static/js/profiles.js"></script>"""

    return HTMLResponse(render_page(f"Edit {profile.domain}", body, request))


@router.post("/profiles/{profile_id}/edit")
async def profile_update(
    request: Request,
    profile_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    label: str | None = Form(default=None),
    cookies_json: str | None = Form(default=None),
    clear_cookies: bool = Form(default=False),
    ua_override: str | None = Form(default=None),
    timeout_seconds: int | None = Form(default=None),
    use_stealth: bool = Form(default=False),
) -> Response:
    """Update a site profile."""
    profile = (
        db.query(SiteProfile)
        .filter(SiteProfile.id == profile_id, SiteProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return HTMLResponse(
            render_page("Not Found", "<p>Profile not found.</p>", request),
            status_code=404,
        )

    profile.label = label or None
    if clear_cookies:
        profile.cookies_json = None
    elif cookies_json:
        profile.cookies_json = cookies_json
    profile.ua_override = ua_override or None
    profile.timeout_seconds = timeout_seconds
    profile.use_stealth = use_stealth

    return RedirectResponse(url="/profiles", status_code=302)


@router.post("/profiles/{profile_id}/delete")
async def profile_delete(
    request: Request,
    profile_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Delete a site profile."""
    profile = (
        db.query(SiteProfile)
        .filter(SiteProfile.id == profile_id, SiteProfile.user_id == user.id)
        .first()
    )
    if profile:
        db.delete(profile)

    return RedirectResponse(url="/profiles", status_code=302)


def _profile_error(message: str, request: Request) -> HTMLResponse:
    body = f"""<div class="card">
  <div class="error-message">{message}</div>
  <p><a href="/profiles">Back to profiles</a></p>
</div>"""
    return HTMLResponse(render_page("Error", body, request))
