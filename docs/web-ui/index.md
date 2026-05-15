---
layout: default
title: Web UI
nav_order: 5
has_children: true
---

# Web UI

Archiveinator includes a browser-based web interface for managing archives, site profiles, RSS feeds, scheduled archiving, and bulk imports. It's served by FastAPI with SQLite storage and APScheduler for background tasks.

---

## Architecture

```
Browser (server-rendered HTML + vanilla JS)
  ├── REST API (FastAPI)
  ├── WebSocket (pipeline progress streaming)
  └── Static file download

FastAPI Server
  ├── Session-based auth (bcrypt-passwords)
  ├── Job Manager (in-process async tasks)
  ├── APScheduler (RSS checks, cron-archiving)
  ├── SQLite via SQLAlchemy
  └── archiveinator pipeline (imported directly)
```

---

## Starting the Server

```bash
# Install with web dependencies
pip3 install "archiveinator[web] @ git+https://github.com/p0rkchop/archiveinator.git"

# Start the server
archiveinator serve

# Custom host and port
archiveinator serve --host 0.0.0.0 --port 8080

# Development mode (auto-reload, verbose logging)
archiveinator serve --dev
```

Open [http://localhost:8080](http://localhost:8080) and register a new account.

---

## Registration and Login

The first user to register is automatically an **admin**. All subsequent users are standard users.

- **Username/password** authentication with bcrypt password hashing
- Session stored in a signed cookie (survives server restarts)
- Passwords must be at least 8 characters
- Optional email address for notifications

---

## Navigation

| Page | Description |
|:-----|:------------|
| [Dashboard](dashboard) | Main page — archive form, progress bar, recent jobs, quick stats |
| [Site Profiles](site-profiles) | Per-domain cookie profiles for authenticated archiving |
| [RSS Feeds](feeds) | Subscribe to RSS/Atom feeds and auto-archive new articles |
| [Schedules](schedules) | Recurring archives on cron schedules |
| [Settings](settings) | Pipeline toggles, user agents, timeouts, email notifications |

The sidebar also links to **History** (past job results with filtering) and **Bulk Import** (multi-format bookmark/URL imports).

---

## Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `RESEND_API_KEY` | _(none)_ | [Resend](https://resend.com) API key for email notifications. If unset, email sending is silently skipped. |
| `RESEND_FROM` | `archiveinator <onboarding@resend.dev>` | From address for notification emails |

---

## Docker

The Docker image includes the web UI and starts the server by default:

```bash
docker run --rm -p 8080:8080 -v archive-data:/data ghcr.io/p0rkchop/archiveinator:latest
```

See the [Docker Guide](../docker) for full details.
