"""Scheduled archive tasks: CRUD for cron-based archiving."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.models import ScheduledTask, SiteProfile
from archiveinator.web.templates import esc_html, render_page

router = APIRouter(tags=["schedules"])


def _cron_presets() -> str:
    return """<div class="cron-presets">
  <button type="button" class="btn btn-sm cron-preset" data-cron="0 * * * *">Every hour</button>
  <button type="button" class="btn btn-sm cron-preset" data-cron="0 8 * * *">Daily 8am</button>
  <button type="button" class="btn btn-sm cron-preset" data-cron="0 8 * * 1-5">Weekdays 8am</button>
  <button type="button" class="btn btn-sm cron-preset" data-cron="*/30 * * * *">Every 30 min</button>
</div>"""


@router.get("/schedules")
async def schedule_list(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """List all scheduled archive tasks for the current user."""
    schedules = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.user_id == user.id)
        .order_by(ScheduledTask.created_at.desc())
        .all()
    )

    rows = ""
    for s in schedules:
        last_run = s.last_run_at.strftime("%Y-%m-%d %H:%M") if s.last_run_at else "Never"
        rows += f"""<tr>
  <td>{esc_html(s.label or s.url[:50])}</td>
  <td><code>{esc_html(s.cron_expression)}</code></td>
  <td>
    <span class="badge {"badge-success" if s.enabled else "badge-pending"}">
      {"Enabled" if s.enabled else "Disabled"}
    </span>
  </td>
  <td>{last_run}</td>
  <td class="actions">
    <form method="post" action="/schedules/{s.id}/toggle" style="display:inline">
      <button type="submit" class="btn btn-sm">
        {"Disable" if s.enabled else "Enable"}
      </button>
    </form>
    <form method="post" action="/schedules/{s.id}/run" style="display:inline">
      <button type="submit" class="btn btn-sm">Run Now</button>
    </form>
    <form method="post" action="/schedules/{s.id}/delete" style="display:inline"
          onsubmit="return confirm('Delete this schedule?')">
      <button type="submit" class="btn btn-sm btn-danger">Delete</button>
    </form>
  </td>
</tr>"""

    if rows:
        table = f"""<table>
<thead><tr>
  <th>URL / Label</th>
  <th>Schedule</th>
  <th>Status</th>
  <th>Last Run</th>
  <th>Actions</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""
    else:
        table = '<p class="empty-state">No scheduled archives yet. <a href="/schedules/new">Create one</a>.</p>'

    body = f"""<div class="card">
  <div class="card-header">
    <h2>Scheduled Archives</h2>
    <a href="/schedules/new" class="btn btn-primary">New Schedule</a>
  </div>
  {table}
</div>"""

    return HTMLResponse(render_page("Schedules", body, request))


@router.get("/schedules/new")
async def schedule_new_form(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Show the create schedule form."""
    profiles = (
        db.query(SiteProfile)
        .filter(SiteProfile.user_id == user.id)
        .order_by(SiteProfile.domain)
        .all()
    )

    profile_options = '<option value="">None (use defaults)</option>'
    for p in profiles:
        profile_options += f'<option value="{p.id}">{esc_html(p.domain)}{" — " + esc_html(p.label) if p.label else ""}</option>'

    body = f"""<div class="card">
  <h2>New Scheduled Archive</h2>
  <form method="post" action="/schedules" class="profile-form">
    <div class="form-group">
      <label for="url">URL</label>
      <input type="url" id="url" name="url" required
             placeholder="https://example.com/article">
    </div>
    <div class="form-group">
      <label for="label">Label (optional)</label>
      <input type="text" id="label" name="label"
             placeholder="Daily news digest">
    </div>
    <div class="form-group">
      <label for="cron_expression">Cron Expression</label>
      <input type="text" id="cron_expression" name="cron_expression" required
             placeholder="0 8 * * *" value="0 8 * * *">
      {_cron_presets()}
      <small class="help-text">Format: minute hour day month day_of_week (e.g. "0 8 * * *" = daily at 8am)</small>
    </div>
    <div class="form-group">
      <label for="site_profile_id">Site Profile</label>
      <select id="site_profile_id" name="site_profile_id">
        {profile_options}
      </select>
    </div>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Create Schedule</button>
      <a href="/schedules" class="btn">Cancel</a>
    </div>
  </form>
</div>

<script>
(function() {{
  document.querySelectorAll('.cron-preset').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      document.getElementById('cron_expression').value = this.dataset.cron;
    }});
  }});
}})();
</script>"""

    return HTMLResponse(render_page("New Schedule", body, request))


@router.post("/schedules")
async def schedule_create(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    url: str = Form(...),
    label: str | None = Form(default=None),
    cron_expression: str = Form(...),
    site_profile_id: int | None = Form(default=None),
) -> Response:
    """Create a new scheduled archive task."""
    url = url.strip()
    cron_expression = cron_expression.strip()

    # Validate cron expression
    try:
        from apscheduler.triggers.cron import CronTrigger

        CronTrigger.from_crontab(cron_expression)
    except (ValueError, TypeError) as e:
        return HTMLResponse(
            render_page(
                "Error",
                f'<div class="card"><p class="error-message">Invalid cron expression: {esc_html(str(e))}</p><a href="/schedules/new" class="btn">Back</a></div>',
                request,
            ),
        )

    # Validate profile ownership
    if site_profile_id is not None:
        profile = (
            db.query(SiteProfile)
            .filter(SiteProfile.id == site_profile_id, SiteProfile.user_id == user.id)
            .first()
        )
        if profile is None:
            return HTMLResponse(
                render_page(
                    "Error",
                    '<div class="card"><p class="error-message">Site profile not found.</p><a href="/schedules/new" class="btn">Back</a></div>',
                    request,
                ),
            )

    schedule = ScheduledTask(
        user_id=user.id,
        url=url,
        label=label or None,
        cron_expression=cron_expression,
        site_profile_id=site_profile_id,
    )
    db.add(schedule)
    db.flush()

    # Register with APScheduler
    from archiveinator.web.scheduler import add_archive_schedule

    add_archive_schedule(
        schedule_id=schedule.id,
        user_id=user.id,
        url=url,
        cron_expression=cron_expression,
        profile_id=site_profile_id,
    )

    return RedirectResponse(url="/schedules", status_code=302)


@router.post("/schedules/{schedule_id}/toggle")
async def schedule_toggle(
    request: Request,
    schedule_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Enable or disable a scheduled task."""
    schedule = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == schedule_id, ScheduledTask.user_id == user.id)
        .first()
    )
    if schedule is None:
        return RedirectResponse(url="/schedules", status_code=302)

    schedule.enabled = not schedule.enabled

    from archiveinator.web.scheduler import add_archive_schedule, remove_archive_schedule

    if schedule.enabled:
        add_archive_schedule(
            schedule_id=schedule.id,
            user_id=user.id,
            url=schedule.url,
            cron_expression=schedule.cron_expression,
            profile_id=schedule.site_profile_id,
        )
    else:
        remove_archive_schedule(schedule.id)

    return RedirectResponse(url="/schedules", status_code=302)


@router.post("/schedules/{schedule_id}/run")
async def schedule_run_now(
    request: Request,
    schedule_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Trigger a scheduled task immediately."""
    schedule = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == schedule_id, ScheduledTask.user_id == user.id)
        .first()
    )
    if schedule is None:
        return RedirectResponse(url="/schedules", status_code=302)

    import asyncio

    from archiveinator.web.scheduler import _run_scheduled_archive

    asyncio.create_task(
        _run_scheduled_archive(
            user_id=user.id,
            url=schedule.url,
            profile_id=schedule.site_profile_id,
            schedule_id=schedule.id,
        )
    )

    return RedirectResponse(url="/schedules", status_code=302)


@router.post("/schedules/{schedule_id}/delete")
async def schedule_delete(
    request: Request,
    schedule_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Delete a scheduled task."""
    schedule = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == schedule_id, ScheduledTask.user_id == user.id)
        .first()
    )
    if schedule is None:
        return RedirectResponse(url="/schedules", status_code=302)

    from archiveinator.web.scheduler import remove_archive_schedule

    remove_archive_schedule(schedule_id)
    db.delete(schedule)

    return RedirectResponse(url="/schedules", status_code=302)
