"""Shared HTML template rendering for all web routes."""

from __future__ import annotations

from fastapi import Request


def render_page(title: str, body: str, request: Request) -> str:
    """Render a full HTML page with shared nav and layout."""
    username = request.session.get("username", "")

    # Build nav links — highlight current section based on title
    nav_links = [
        ("/dashboard", "Dashboard", {"dashboard"}),
        ("/profiles", "Profiles", {"profiles"}),
        ("/jobs", "History", {"history", "jobs"}),
        ("/schedules", "Schedules", {"schedules"}),
        ("/feeds", "Feeds", {"feeds"}),
        ("/config", "Settings", {"config", "settings"}),
    ]

    nav_html = ""
    for href, label, keywords in nav_links:
        active = any(k in title.lower() for k in keywords)
        cls = ' class="nav-link active"' if active else ' class="nav-link"'
        nav_html += f'  <a href="{href}"{cls}>{label}</a>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — archiveinator</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
<nav class="nav">
  <a href="/dashboard" class="nav-brand">archiveinator</a>
{nav_html}  <span class="nav-user">{username}</span>
  <form method="post" action="/auth/logout" style="display:inline">
    <button type="submit" class="nav-logout">Log out</button>
  </form>
</nav>
<div class="content">
{body}
</div>
</body>
</html>"""
