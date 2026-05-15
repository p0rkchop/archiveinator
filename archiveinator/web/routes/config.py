"""User config settings: pipeline steps, UA list, timeouts."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from archiveinator.config import DEFAULT_PIPELINE
from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.models import UserConfig
from archiveinator.web.templates import render_page

router = APIRouter(tags=["config"])


def _get_or_create_config(user_id: int, db: Any) -> UserConfig:
    """Return existing config or create a default one."""
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    if config is not None:
        return config  # type: ignore[no-any-return]

    config = UserConfig(
        user_id=user_id,
        pipeline_json=json.dumps(
            [{"step": s.step, "enabled": s.enabled} for s in DEFAULT_PIPELINE]
        ),
        ua_list_json=json.dumps(
            [
                {
                    "name": "chrome_desktop",
                    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "enabled": True,
                },
                {
                    "name": "googlebot",
                    "ua": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                    "enabled": False,
                },
                {
                    "name": "bingbot",
                    "ua": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingcrawl.htm)",
                    "enabled": False,
                },
            ]
        ),
    )
    db.add(config)
    return config


def _pipeline_checkbox(step: dict[str, Any]) -> str:
    checked = " checked" if step["enabled"] else ""
    disabled = " disabled" if step["step"] in ("page_load", "asset_inlining") else ""
    return (
        f'<label class="pipeline-step">'
        f'<input type="checkbox" name="pipeline_{step["step"]}" value="1"{checked}{disabled}>'
        f'<span class="step-name">{step["step"]}</span>'
        f"</label>"
    )


@router.get("/config")
async def config_page(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Show the user config settings page."""
    config = _get_or_create_config(user.id, db)

    pipeline = json.loads(config.pipeline_json) if config.pipeline_json else []
    pipeline_html = ""
    for s in pipeline:
        pipeline_html += _pipeline_checkbox(s)

    ua_list = json.loads(config.ua_list_json) if config.ua_list_json else []
    ua_rows = ""
    for i, ua in enumerate(ua_list):
        checked = " checked" if ua.get("enabled", True) else ""
        ua_rows += f"""<tr>
  <td><input type="checkbox" name="ua_enabled_{i}" value="1"{checked}></td>
  <td><input type="text" name="ua_name_{i}" value="{ua.get("name", "")}" class="input-sm"></td>
  <td><input type="text" name="ua_value_{i}" value="{ua.get("ua", "")}" class="input-sm ua-value"></td>
</tr>"""

    body = f"""<div class="card">
  <h2>Settings</h2>
  <form method="post" action="/config" class="config-form">

    <fieldset>
      <legend>Pipeline Steps</legend>
      <p class="help-text">Enable or disable pipeline steps. "page_load" and "asset_inlining" are required.</p>
      <div class="pipeline-grid">
        {pipeline_html}
      </div>
    </fieldset>

    <fieldset>
      <legend>User Agents</legend>
      <div class="form-group checkbox-group">
        <label>
          <input type="checkbox" name="ua_cycle_enabled" value="1"
                 {"checked" if config.ua_cycle_enabled else ""}>
          Enable UA cycling (rotate user agents on retries)
        </label>
      </div>
      <table class="ua-table">
        <thead><tr>
          <th>Enabled</th>
          <th>Name</th>
          <th>User-Agent String</th>
        </tr></thead>
        <tbody>{ua_rows}</tbody>
      </table>
    </fieldset>

    <fieldset>
      <legend>Notifications</legend>
      <div class="form-group checkbox-group">
        <label>
          <input type="checkbox" name="email_notifications_enabled" value="1"
                 {"checked" if config.email_notifications_enabled else ""}>
          Send email notifications on archive completion/failure
        </label>
      </div>
      <div class="form-group">
        <label for="email_address">Email address (set during registration)</label>
        <input type="email" id="email_address" value="{user.email or ""}" disabled class="input-sm">
        <p class="help-text">Update your email on the registration page. Leave blank to use the address provided at sign-up.</p>
      </div>
    </fieldset>

    <fieldset>
      <legend>General</legend>
      <div class="form-group">
        <label for="timeout_seconds">Page Load Timeout (seconds)</label>
        <input type="number" id="timeout_seconds" name="timeout_seconds"
               min="5" max="300" value="{config.timeout_seconds}">
      </div>
      <div class="form-group">
        <label for="output_retention_days">Auto-delete archives after (days, 0 = keep forever)</label>
        <input type="number" id="output_retention_days" name="output_retention_days"
               min="0" max="365" value="{config.output_retention_days or 0}">
      </div>
    </fieldset>

    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Save Settings</button>
      <a href="/dashboard" class="btn">Cancel</a>
    </div>
  </form>
</div>"""

    return HTMLResponse(render_page("Settings", body, request))


@router.post("/config")
async def config_save(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    ua_cycle_enabled: bool = Form(default=False),
    timeout_seconds: int = Form(default=40),
    output_retention_days: int = Form(default=0),
    email_notifications_enabled: bool = Form(default=False),
) -> Response:
    """Save user config settings."""
    config = _get_or_create_config(user.id, db)

    # Parse pipeline from form fields
    form_data = await request.form()
    existing_pipeline = json.loads(config.pipeline_json) if config.pipeline_json else []
    for step in existing_pipeline:
        field_name = f"pipeline_{step['step']}"
        if step["step"] in ("page_load", "asset_inlining"):
            step["enabled"] = True
        else:
            step["enabled"] = field_name in form_data

    config.pipeline_json = json.dumps(existing_pipeline)

    # Parse UA list from form fields
    ua_count = 0
    while f"ua_name_{ua_count}" in form_data or f"ua_value_{ua_count}" in form_data:
        ua_count += 1

    ua_list = []
    for i in range(ua_count):
        name = form_data.get(f"ua_name_{i}")
        value = form_data.get(f"ua_value_{i}")
        if name and value:
            ua_list.append(
                {
                    "name": name,
                    "ua": value,
                    "enabled": f"ua_enabled_{i}" in form_data,
                }
            )

    config.ua_list_json = json.dumps(ua_list) if ua_list else None
    config.ua_cycle_enabled = ua_cycle_enabled
    config.timeout_seconds = timeout_seconds
    config.output_retention_days = output_retention_days if output_retention_days > 0 else None
    config.email_notifications_enabled = email_notifications_enabled

    return RedirectResponse(url="/config", status_code=302)
