# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## File Access Rules

- **Only search and operate on files within the project directory** (`/Users/chris/code/archiveinator/`).
- Do **not** access, search, or read files outside the project directory — including home folder subdirectories (Music, Documents, Downloads, Library, etc.).
- When locating runtime files (config, caches), use the known path directly (e.g. via Python/`platformdirs`) rather than broad filesystem searches like `find ~`.

## Commands

```bash
# Development install
pip3 install -e ".[dev]"

# Run tests (CI-safe, no network, unit only)
pytest tests/unit/ -q --tb=short

# Run specific test file
pytest tests/unit/test_paywall.py -q

# Run mock paywall QA tests (local network only)
pytest tests/qa/test_mock_paywall.py -m mock_paywall

# Run real-URL paywall tests (requires network + full setup)
pytest tests/qa/test_real_urls.py -m real_url

# Lint & format
ruff check .
ruff format --check .

# Type check
mypy archiveinator/

# Docker build (local test)
docker build -t archiveinator:test .

# First-time setup (installs Chromium, monolith, blocklists)
archiveinator setup

# Web: start dev server (install with `pip3 install -e ".[dev,web]"`)
archiveinator serve --dev

# Web: build Docker image
docker build -t archiveinator:web-test .
```

**Dependency management**: This project uses `uv`. To add/update deps, edit `pyproject.toml` and run `uv sync`. The `uv.lock` file is committed and provides reproducible installs.

## Architecture

The core concept is a **sequential pipeline** of async steps, each receiving and mutating an `ArchiveContext` dataclass (`pipeline.py`). Steps are user-configurable (enabled/disabled in YAML config) with two hard constraints: `page_load` must be first and `asset_inlining` must be last.

### Data flow

```
URL → page_load → [paywall detection] → [bypass strategies] → image_dedup → asset_inlining → HTML file
```

**`archiveinator/cli.py`** — Entry point. Orchestrates the pipeline, handles retry/bypass loop via `_run_paywall_bypass()`.

**`archiveinator/pipeline.py`** — Defines `ArchiveContext` (shared mutable state) and `run_pipeline()`.

**`archiveinator/config.py`** — Loads/validates YAML config from platform-specific dirs. Auto-migrates existing configs when new pipeline steps are added in a new version.

**`archiveinator/steps/`** — One file per pipeline step:
- `page_load.py` — Playwright Chromium; soft-blocks if bot-challenge/paywall detected
- `paywall.py` — Detection via HTTP status (401/402/403/429), DOM selectors for known bot-challenge vendors (Cloudflare, PerimeterX, DataDome, Akamai), and word count
- `js_overlay.py` — Strips paywall modal overlays from live DOM before serialization
- `stealth_browser.py` — Anti-fingerprinting patches (playwright-stealth); only invoked for bot challenges
- `ad_blocking.py` — Network-level request interception (EasyList + EasyPrivacy)
- `dom_cleanup.py` — Removes ad DOM nodes (Google Ads, DFP, Taboola, tracking pixels)
- `google_news.py` — Retry with Google News referer header
- `content_extraction.py` — trafilatura fallback for article text extraction
- `archive_fallback.py` — Queries Wayback Machine then archive.today as last resort
- `image_dedup.py` — Collapses `<picture>`/`srcset` to single URL ≤1200px
- `asset_inlining.py` — Shells out to the `monolith` binary to produce a single-file HTML

**`archiveinator/bypass_cache.py`** — Per-domain YAML cache of which bypass strategy succeeded. Checked before running the full bypass suite.

**`archiveinator/ua_manager.py`** — Tracks which user agents work per domain; drives UA cycling strategy.

**`archiveinator/naming.py`** — Output filename format: `YYYY-MM-DD_HH-MM_hostname_title[_partial].html`

**`archiveinator/setup_cmd.py`** — Downloads Playwright Chromium, the platform-appropriate `monolith` binary from GitHub releases, and ad-block rule files.

### Web Architecture (`archiveinator/web/`)

FastAPI application with server-rendered HTML (no Jinja2 — templates are Python f-strings via `templates.py`).

**Key modules:**
- **`app.py`** — Application factory, lifespan (DB tables, scheduler startup/shutdown), router registration
- **`auth.py`** — Session-based auth via bcrypt + signed cookies (`get_current_user` FastAPI dependency)
- **`db.py`** — SQLAlchemy engine + session factory (SQLite at `{data_dir}/archiveinator.db`)
- **`models.py`** — 7 ORM models: `User`, `SiteProfile`, `UserConfig`, `ArchiveJob`, `RssFeed`, `FeedItem`, `ScheduledTask`
- **`job_manager.py`** — In-process async job lifecycle (singleton), WebSocket progress streaming via `asyncio.Queue`
- **`scheduler.py`** — APScheduler `AsyncIOScheduler` for cron-based archiving + RSS feed polling
- **`feed_reader.py`** — Feedparser wrapper; `check_feed()` runs in thread executor, `check_all_feeds()` iterates all feeds
- **`emailer.py`** — Resend.com email integration; `RESEND_API_KEY` env var, graceful skip when unset
- **`templates.py`** — Shared `render_page()` with nav bar rendering and active-page highlighting

**Routes** (`archiveinator/web/routes/`):
- `archive.py` — POST /archive, GET /archive/{id}, WS /archive/{id}/ws, GET /download/{id}
- `auth.py` — POST /auth/register, /auth/login, /auth/logout
- `profiles.py` — CRUD site profiles with cookie file upload
- `config.py` — Pipeline steps, UA list, timeouts, email notification toggle
- `jobs.py` — Paginated job history with status/domain filtering
- `schedules.py` — CRUD cron schedules with presets
- `feeds.py` — CRUD RSS feeds, force-check, item list
- `bulk.py` — Bulk import (bookmarks HTML, plain text, CSV) with progress tracking

**Tech constraints:**
- `from __future__ import annotations` in all route files (PEP 563)
- Use `: Any` for `Depends()` params (FastAPI/Pydantic v2 can't see SQLAlchemy types)
- Return types use `Response` (never unions like `HTMLResponse | RedirectResponse`)

### External binary dependency

`monolith` is not installed via pip. It is downloaded at `archiveinator setup` time from this repo's own GitHub releases (cross-compiled in CI). The release workflow cross-compiles monolith from source for macOS (arm64) and Linux (x86_64/arm64).

## Versioning & Releases

- **SemVer** (`MAJOR.MINOR.PATCH`) managed in `pyproject.toml`
- **To release**: bump `version` in `pyproject.toml`, commit, then push a tag `v<version>`. The `release.yml` workflow builds all platform binaries and creates the GitHub release automatically.
- No manual release steps; the tag push is the sole trigger.

## Issue & Milestone Management

Issues use a structured label system:
- **Type**: `type:feature`, `type:bug`, `type:enhancement`, `type:ci`, `type:docs`
- **Area**: `area:pipeline`, `area:paywall`, `area:ad-blocking`, `area:config`, `area:cli`, `area:packaging`, `area:testing`
- **Priority**: `p1:high`, `p2:normal`, `p3:low`

Work is organized into milestones named after upcoming versions (e.g., `v0.4.0`). Open issues should be assigned to the relevant milestone before starting work.

## CI

- **`ci.yml`**: Runs on push/PR to main. Tests on Python 3.11 and 3.12 via `uv`. Excludes `e2e` and `real_url` marked tests. Also runs ruff, mypy, and a Docker build test (no push).
- **`qa-paywall.yml`**: Scheduled weekly (Monday 06:00 UTC); runs real-URL paywall tests and auto-opens a GitHub issue on failure.
- **`update-blocklists.yml`**: Scheduled weekly; refreshes EasyList/EasyPrivacy and commits them back.

## GitHub Actions Monitoring

- **Monitor CI after every push**: After `git push`, check the triggered GitHub Actions run (`gh run list --limit 1`) and wait for it to complete (`gh run watch <run-id>`). Do not proceed with further work until CI passes.
- **Automatically fix failures**: If CI fails, immediately investigate logs, reproduce locally, fix linting (`ruff check --fix`, `ruff format .`), type errors, or test failures, then commit and push fixes.
- **Release workflow monitoring**: After pushing a version tag, monitor the release workflow through completion. Verify all three platform binaries and the Docker image are built and the release is published.

## Release Process & Quality Assurance

### Two-Action Release Flow
When releasing a new version, two GitHub Actions run in sequence:

1. **CI workflow** (`ci.yml`) – triggered by push to `main`
   - Runs tests, linting (`ruff check`, `ruff format --check`), and type checking (`mypy`)
   - **Must pass** before proceeding with release
   - If CI fails, fix the issues locally and push again

2. **Release workflow** (`release.yml`) – triggered by `v*` tag push
   - Builds `monolith` binaries for macOS arm64 and Linux (x86_64/arm64)
   - Builds and pushes a multi-arch Docker image to `ghcr.io`
   - Creates GitHub release with binaries as assets
   - Only runs after CI passes (manual tag push follows CI success)

### Mandatory Linting Compliance
- **Always run local checks before pushing**:
  ```bash
  ruff check .
  ruff format --check .
  mypy archiveinator/
  pytest tests/ -m "not e2e and not real_url" -q --tb=short
  ```
- **If CI fails**, immediately diagnose and fix:
  1. Check GitHub Actions run output for specific failures
  2. Reproduce locally with the commands above
  3. Fix linting (`ruff check --fix`, `ruff format .`) and type errors
  4. Commit fixes and push again
  5. **Do not push tags** until CI passes
- **Monitor release workflow** through completion:
  - Wait for all four platform builds to finish
  - Verify release appears at `https://github.com/p0rkchop/archiveinator/releases/tag/vX.Y.Z`
  - Test downloaded binaries if needed

### Why Two Workflows?
- **Separation of concerns**: CI validates code quality; Release builds distributables
- **Safety net**: Prevents releasing broken code (CI must pass first)
- **Efficiency**: Release builds can run in parallel across platforms while CI runs once
