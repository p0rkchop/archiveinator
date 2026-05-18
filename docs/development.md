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
  archiveinator/
    cli.py                # CLI entry point (archive, setup, login, serve, ladder, cache)
    config.py             # Config model, defaults, YAML migration
    pipeline.py           # ArchiveContext dataclass
    bypass_cache.py       # Per-domain bypass strategy cache (YAML)
    ua_manager.py         # UA cycling and per-domain tracking
    naming.py             # Output filename format
    setup_cmd.py          # archiveinator setup logic
    blocklist.py          # EasyList/EasyPrivacy loading
    steps/
      page_load.py        # Playwright page load + ad blocking + paywall detection
      paywall.py          # Paywall/bot detection logic
      js_overlay.py       # JS overlay/modal removal (93 selectors)
      stealth_browser.py  # playwright-stealth anti-fingerprinting
      ad_blocking.py      # Network-level request interception
      dom_cleanup.py      # DOM ad node removal
      google_news.py      # Google News referrer bypass
      header_tricks.py    # Googlebot UA + header spoofing
      ua_cycling.py       # User agent cycling bypass
      image_dedup.py      # picture/srcset deduplication
      asset_inlining.py   # monolith binary integration
      content_extraction.py  # trafilatura text fallback
      archive_fallback.py # Wayback Machine + archive.today fallback
    web/
      app.py              # FastAPI factory, lifespan, middleware
      auth.py             # Session auth, bcrypt
      db.py               # SQLAlchemy engine + session factory
      models.py           # 7 ORM models (User, ArchiveJob, SiteProfile, ...)
      job_manager.py      # Async job lifecycle + WebSocket progress streaming
      scheduler.py        # APScheduler: cron schedules + RSS polling
      feed_reader.py      # feedparser RSS/Atom parsing
      emailer.py          # Resend.com email notifications
      templates.py        # render_page() and HTML helpers
      routes/
        archive.py        # POST /archive, WS /archive/{id}/ws, GET /download/{id}
        auth.py           # /auth/register, /auth/login, /auth/logout
        bulk.py           # Bulk import (bookmarks HTML, text, CSV)
        config.py         # User pipeline settings
        dashboard.py      # Main dashboard
        feeds.py          # RSS feed management
        jobs.py           # Archive history
        profiles.py       # Site profiles + cookie upload
        schedules.py      # Cron schedule management
      static/             # CSS and JavaScript
  tests/
    unit/                 # Fast tests (no network, no browser)
    qa/
      test_mock_paywall.py   # Mock HTTP server paywall scenarios
      test_real_urls.py      # Live site bypass validation
      sites.yaml             # 80+ paywalled site catalog
  docs/                   # GitHub Pages (Just the Docs)
```

---

## Running Tests

```bash
# Unit tests (fast, no network required)
pytest tests/unit/ -q

# Mock paywall tests (local server, no external network)
pytest tests/qa/test_mock_paywall.py -m mock_paywall -q

# Real-URL tests (requires network + full setup)
pytest tests/qa/test_real_urls.py -m real_url -q

# Filter real-URL tests by difficulty or paywall type
pytest tests/qa/test_real_urls.py -m real_url --qa-difficulty easy
pytest tests/qa/test_real_urls.py -m real_url --qa-paywall-type piano
pytest tests/qa/test_real_urls.py -m real_url --qa-site "NYT"
```

---

## Lint and Type Check

```bash
# Lint
ruff check .

# Format check
ruff format --check .

# Auto-fix lint and format
ruff check --fix . && ruff format .

# Type check
mypy archiveinator/
```

---

## Researching a New Paywalled Site

Use `archiveinator ladder` to quickly test header/referrer bypass combinations without modifying code:

```bash
# Start the Ladder proxy (requires Docker)
archiveinator ladder

# Test in a separate terminal
curl http://localhost:8181/https://target-site.com
curl http://localhost:8181/api/https://target-site.com | jq '.body' | wc -w

# Iterate with a YAML rule file
# ~/.config/archiveinator/ladder-rules/target.yaml
```

See [Paywall Bypass → Researching a New Site](../paywall-bypass/#researching-a-new-paywalled-site) for the full workflow.

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

GitHub Actions workflows:

| Workflow | Trigger | Jobs |
|:---------|:--------|:-----|
| `ci.yml` | Push / PR to main | Tests (Python 3.12), Lint + Type check, Docker build test |
| `release.yml` | `v*` tag push | Build monolith binaries, create GitHub Release, build + push Docker image |
| `qa-paywall.yml` | Weekly (Mon 06:00 UTC) | Real-URL paywall bypass tests; opens issue on failure |
| `update-blocklists.yml` | Weekly (Mon 03:00 UTC) | Refresh EasyList + EasyPrivacy, commit back |

---

## Release Process

1. Bump `version` in `pyproject.toml` and `archiveinator/web/app.py`
2. Run `uv lock` to update the lockfile
3. Commit: `git commit -m "release: bump to vX.Y.Z"`
4. Push: `git push origin main`
5. Wait for CI to pass
6. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`
7. The release workflow builds binaries, Docker image, and creates the GitHub Release automatically

---

## Documentation

Documentation lives in `docs/` and is published via GitHub Pages using the [Just the Docs](https://just-the-docs.com/) theme. Pages deploy automatically from the main branch `/docs` folder after every push.

To preview locally, install Jekyll and run `bundle exec jekyll serve` in the `docs/` directory.
