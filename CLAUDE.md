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

# Run tests (CI-safe, no network)
pytest tests/ -m "not e2e and not real_url" -q --tb=short

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

# First-time setup (installs Chromium, monolith, blocklists)
archiveinator setup
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

### External binary dependency

`monolith` is not installed via pip. It is downloaded at `archiveinator setup` time from this repo's own GitHub releases (cross-compiled in CI). The release workflow cross-compiles monolith from source for macOS (arm64), Linux (x86_64/arm64), and Windows (x86_64).

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

- **`ci.yml`**: Runs on push/PR to main. Tests on Python 3.11 and 3.12 via `uv`. Excludes `e2e` and `real_url` marked tests. Also runs ruff and mypy.
- **`qa-paywall.yml`**: Scheduled weekly (Monday 06:00 UTC); runs real-URL paywall tests and auto-opens a GitHub issue on failure.
- **`update-blocklists.yml`**: Scheduled weekly; refreshes EasyList/EasyPrivacy and commits them back.
