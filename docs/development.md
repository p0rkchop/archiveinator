---
layout: default
title: Development
nav_order: 9
---

# Development

Set up a local development environment for contributing to archiveinator.

---

## Dev Setup

```bash
# Clone the repo
git clone https://github.com/p0rkchop/archiveinator.git
cd archiveinator

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with dev and web dependencies
pip3 install -e ".[dev,web]"

# Run setup (installs Chromium, monolith, blocklists)
archiveinator setup
```

---

## Project Structure

```
archiveinator/
  archiveinator/          # Main package
    __init__.py
    cli.py                # CLI commands (archive, setup, login, serve)
    config.py             # Config model, defaults, migration
    pipeline.py           # Pipeline runner and step registry
    archive.py            # Core archive logic
    asset_inlining.py     # monolith integration
    web/                  # Web UI (FastAPI)
      __init__.py
      app.py              # FastAPI app factory, middleware
      auth.py             # Password hashing, session management
      db.py               # SQLAlchemy engine/session
      models.py           # All 7 database models
      job_manager.py      # In-memory job lifecycle + WebSocket events
      feed_reader.py      # RSS/Atom feed parsing + polling
      scheduler.py        # APScheduler for feeds + scheduled archiving
      emailer.py          # Resend.com email integration
      templates.py        # HTML templating helpers
      routes/             # Route handlers
        archive.py        # POST /archive, WS /archive/{id}/ws, GET /download/{id}
        auth.py           # /auth/register, /auth/login, /auth/logout
        bulk.py           # POST /bulk (multi-format import)
        config.py         # GET/PUT /config (user settings)
        dashboard.py      # GET /dashboard (main page)
        feeds.py          # CRUD /feeds
        jobs.py           # GET /jobs (history)
        profiles.py       # CRUD /profiles
        schedules.py      # CRUD /schedules
      static/             # CSS, JS
      templates/          # Jinja2 templates (rendered server-side)
  tests/
    unit/                 # Fast unit tests (no network)
    integration/          # Tests requiring network + Playwright
```

---

## Running Tests

```bash
# Unit tests (fast, no network required)
pytest tests/unit/

# Integration tests (require network + Playwright Chromium)
pytest tests/integration/

# All tests
pytest tests/
```

---

## Lint and Type Check

```bash
# Lint
ruff check .

# Format check
ruff format --check .

# Type check
mypy archiveinator/
```

---

## Web UI Development

```bash
# Install web dependencies
pip3 install -e ".[dev,web]"

# Start with auto-reload and verbose logging
archiveinator serve --dev
```

The SQLite database is created at the platform data directory on first startup (alongside `config.yaml`). Sessions survive server restarts when using a persistent `/data` mount in Docker.

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):

| Job | Description |
|:----|:------------|
| `test` | Runs unit tests on Python 3.12 |
| `lint` | Ruff lint + format check, mypy type check |
| `release` | Builds and publishes Docker image on tag push |

---

## Release Process

1. Bump version in `pyproject.toml`
2. Commit and push
3. Tag the commit: `git tag v0.X.Y`
4. Push the tag: `git push origin v0.X.Y`
5. The release workflow builds the Docker image, creates a GitHub Release, and publishes to ghcr.io

---

## Documentation

Documentation lives in the `docs/` folder and is published via GitHub Pages using the [Just the Docs](https://just-the-docs.com/) theme. Pages deploy automatically from the main branch `/docs` folder.
