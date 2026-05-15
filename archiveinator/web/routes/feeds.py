"""Feed management: CRUD for RSS/Atom feeds."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from archiveinator.web.auth import get_current_user
from archiveinator.web.db import get_session
from archiveinator.web.models import FeedItem, RssFeed, SiteProfile
from archiveinator.web.templates import esc_html, render_page

router = APIRouter(tags=["feeds"])


@router.get("/feeds")
async def feed_list(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """List all RSS feeds for the current user."""
    feeds = (
        db.query(RssFeed)
        .filter(RssFeed.user_id == user.id)
        .order_by(RssFeed.created_at.desc())
        .all()
    )

    rows = ""
    for f in feeds:
        item_count = db.query(FeedItem).filter(FeedItem.feed_id == f.id).count()
        last_checked = (
            f.last_checked_at.strftime("%Y-%m-%d %H:%M") if f.last_checked_at else "Never"
        )

        feed_display = esc_html(f.label or f.feed_url[:50])
        feed_url_display = esc_html(f.feed_url[:60])
        rows += f"""<tr>
  <td>{feed_display}</td>
  <td class="cell-url"><a href="{f.feed_url}" target="_blank" rel="noopener">{feed_url_display}</a></td>
  <td>{item_count}</td>
  <td>{last_checked}</td>
  <td class="actions">
    <form method="post" action="/feeds/{f.id}/check" style="display:inline">
      <button type="submit" class="btn btn-sm">Check Now</button>
    </form>
    <a href="/feeds/{f.id}/items" class="btn btn-sm">Items</a>
    <form method="post" action="/feeds/{f.id}/delete" style="display:inline"
          onsubmit="return confirm('Remove this feed and all its items?')">
      <button type="submit" class="btn btn-sm btn-danger">Remove</button>
    </form>
  </td>
</tr>"""

    if rows:
        table = f"""<table>
<thead><tr>
  <th>Feed</th>
  <th>URL</th>
  <th>Items</th>
  <th>Last Checked</th>
  <th>Actions</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""
    else:
        table = '<p class="empty-state">No RSS feeds yet. <a href="/feeds/new">Add one</a>.</p>'

    body = f"""<div class="card">
  <div class="card-header">
    <h2>RSS Feeds</h2>
    <a href="/feeds/new" class="btn btn-primary">Add Feed</a>
  </div>
  {table}
</div>"""

    return HTMLResponse(render_page("Feeds", body, request))


@router.get("/feeds/new")
async def feed_new_form(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Show the add feed form."""
    profiles = (
        db.query(SiteProfile)
        .filter(SiteProfile.user_id == user.id)
        .order_by(SiteProfile.domain)
        .all()
    )

    profile_options = '<option value="">None (use defaults)</option>'
    for p in profiles:
        profile_options += (
            f'<option value="{p.id}">{p.domain}{" — " + p.label if p.label else ""}</option>'
        )

    body = f"""<div class="card">
  <h2>Add RSS Feed</h2>
  <p class="help-text">New articles from this feed will be automatically archived.</p>
  <form method="post" action="/feeds" class="profile-form">
    <div class="form-group">
      <label for="feed_url">Feed URL</label>
      <input type="url" id="feed_url" name="feed_url" required
             placeholder="https://example.com/rss">
    </div>
    <div class="form-group">
      <label for="label">Label (optional)</label>
      <input type="text" id="label" name="label"
             placeholder="Tech News">
    </div>
    <div class="form-group">
      <label for="site_profile_id">Site Profile</label>
      <select id="site_profile_id" name="site_profile_id">
        {profile_options}
      </select>
      <small class="help-text">Profile to use when archiving articles from this feed.</small>
    </div>
    <div class="form-group">
      <label for="check_interval_minutes">Check Interval (minutes)</label>
      <input type="number" id="check_interval_minutes" name="check_interval_minutes"
             min="5" max="1440" value="60">
    </div>
    <div class="form-actions">
      <button type="submit" class="btn btn-primary">Add Feed</button>
      <a href="/feeds" class="btn">Cancel</a>
    </div>
  </form>
</div>"""

    return HTMLResponse(render_page("Add Feed", body, request))


@router.post("/feeds")
async def feed_create(
    request: Request,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
    feed_url: str = Form(...),
    label: str | None = Form(default=None),
    site_profile_id: int | None = Form(default=None),
    check_interval_minutes: int = Form(default=60),
) -> Response:
    """Add a new RSS feed."""
    feed_url = feed_url.strip()

    if not feed_url.startswith(("http://", "https://")):
        return RedirectResponse(url="/feeds", status_code=302)

    # Check for duplicate
    existing = (
        db.query(RssFeed).filter(RssFeed.user_id == user.id, RssFeed.feed_url == feed_url).first()
    )
    if existing:
        # Redirect back with error — for simplicity, just redirect
        return RedirectResponse(url="/feeds", status_code=302)

    feed = RssFeed(
        user_id=user.id,
        feed_url=feed_url,
        label=label or None,
        site_profile_id=site_profile_id,
        check_interval_minutes=max(5, min(1440, check_interval_minutes)),
    )
    db.add(feed)

    return RedirectResponse(url="/feeds", status_code=302)


@router.post("/feeds/{feed_id}/check")
async def feed_check_now(
    request: Request,
    feed_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Force an immediate check of a feed."""
    feed = db.query(RssFeed).filter(RssFeed.id == feed_id, RssFeed.user_id == user.id).first()
    if feed is not None:
        # Run synchronously (fast for typical feeds)
        import threading

        from archiveinator.web.feed_reader import check_feed

        threading.Thread(target=check_feed, args=(feed_id,), daemon=True).start()

    return RedirectResponse(url="/feeds", status_code=302)


@router.post("/feeds/{feed_id}/delete")
async def feed_delete(
    request: Request,
    feed_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """Remove a feed and its items."""
    feed = db.query(RssFeed).filter(RssFeed.id == feed_id, RssFeed.user_id == user.id).first()
    if feed is not None:
        db.delete(feed)

    return RedirectResponse(url="/feeds", status_code=302)


@router.get("/feeds/{feed_id}/items")
async def feed_items(
    request: Request,
    feed_id: int,
    user: Any = Depends(get_current_user),
    db: Any = Depends(get_session),
) -> Response:
    """List items for a feed."""
    feed = db.query(RssFeed).filter(RssFeed.id == feed_id, RssFeed.user_id == user.id).first()
    if feed is None:
        return HTMLResponse(
            render_page("Not Found", "<p>Feed not found.</p>", request),
            status_code=404,
        )

    items = (
        db.query(FeedItem)
        .filter(FeedItem.feed_id == feed_id)
        .order_by(FeedItem.published_at.desc())
        .limit(100)
        .all()
    )

    rows = ""
    for item in items:
        published = item.published_at.strftime("%Y-%m-%d") if item.published_at else "—"
        status = ""
        if item.job_id:
            status = f'<a href="/download/{item.job_id}" class="btn btn-sm">View</a>'
        rows += f"""<tr>
  <td class="cell-url"><a href="{item.url}" target="_blank" rel="noopener">{esc_html(item.title or item.url[:60])}</a></td>
  <td>{published}</td>
  <td>{"Archived" if item.archived else "Pending"}</td>
  <td>{status}</td>
</tr>"""

    table = ""
    if rows:
        table = f"""<table>
<thead><tr>
  <th>Article</th>
  <th>Published</th>
  <th>Status</th>
  <th>Archive</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""
    else:
        table = '<p class="empty-state">No items found for this feed.</p>'

    body = f"""<div class="card">
  <div class="card-header">
    <h2>Feed Items: {esc_html(feed.label or feed.feed_url)}</h2>
    <a href="/feeds" class="btn">Back to Feeds</a>
  </div>
  {table}
</div>"""

    return HTMLResponse(render_page("Feed Items", body, request))
