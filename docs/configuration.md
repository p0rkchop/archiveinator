---
layout: default
title: Configuration
nav_order: 4
---

# Configuration

The config file is created automatically at first run by `archiveinator setup`. It uses YAML format with sensible defaults.

## Config File Location

| Platform | Path |
|:---------|:-----|
| macOS | `~/Library/Application Support/archiveinator/config.yaml` |
| Linux | `~/.config/archiveinator/config.yaml` |

---

## Full Configuration Reference

```yaml
# Directory where archived files are saved (default: current working directory)
output_dir: .

# Maximum asset size to inline in MB (images, CSS, fonts — audio/video always skipped)
asset_size_limit_mb: 5

# Page load timeout in seconds
timeout_seconds: 40

# How often to auto-refresh adblock blocklists (in days)
blocklist_update_interval_days: 7

user_agents:
  # Set to true to enable UA cycling as a paywall bypass strategy
  cycle: false
  agents:
    - name: chrome_desktop
      enabled: true
      ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    - name: googlebot
      enabled: false
      ua: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    - name: bingbot
      enabled: false
      ua: "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingcrawl.htm)"

# Stealth browser fingerprint settings (used when stealth_browser or patchright_load fires)
stealth:
  viewport_width: 1920
  viewport_height: 1080
  locale: "en-US"
  timezone: "America/New_York"

# Optional: URL of a running FlareSolverr instance for Cloudflare bypass.
# Also reads FLARESOLVERR_URL env var. Leave commented out to disable (default).
# flaresolverr_url: "http://localhost:8191/v1"

pipeline:
  - step: network_ad_blocking
    enabled: true
  - step: page_load
    enabled: true
  - step: paywall_detection
    enabled: true
  - step: js_overlay_removal
    enabled: true
  - step: js_disabled
    enabled: true
  # Retries with playwright-stealth anti-fingerprinting (JS-layer patches)
  - step: stealth_browser
    enabled: true
  # Retries with CDP-patched Chromium — bypasses PerimeterX/DataDome binary detection
  # Requires: pip install patchright && python -m patchright install chromium
  - step: patchright_load
    enabled: true
  # Obtains cf_clearance cookie from a running FlareSolverr sidecar
  # Only fires when Cloudflare is detected AND flaresolverr_url is configured
  - step: flaresolverr
    enabled: true
  # Retries with patched Firefox engine — different TLS/HTTP2/canvas fingerprint from Chromium
  # Requires: pip install camoufox && python -m camoufox fetch
  - step: camoufox_load
    enabled: true
  - step: ua_cycling
    enabled: true
  - step: header_tricks
    enabled: true
  - step: google_news
    enabled: true
  - step: dom_ad_cleanup
    enabled: true
  - step: image_dedup
    enabled: true
  - step: content_extraction
    enabled: true
  - step: archive_fallback
    enabled: true
  - step: asset_inlining
    enabled: true
```

---

## Pipeline Steps

See the full [Pipeline](pipeline) documentation for a detailed explanation of each step.

| Step | Default | Description |
|:-----|:--------|:------------|
| `network_ad_blocking` | ✅ on | Intercepts network requests and blocks ads/trackers using EasyList + EasyPrivacy before they're fetched |
| `page_load` | ✅ on | Loads the page in a headless Chromium browser and waits for network idle |
| `paywall_detection` | ✅ on | Detects paywalls via HTTP status, DOM selectors, and word count — runs inside the browser |
| `js_overlay_removal` | ✅ on | Removes JS-rendered paywall modals and overlays from the live DOM; restores body scroll |
| `js_disabled` | ✅ on | Retries page load with JavaScript disabled — bypasses some client-side paywalls |
| `stealth_browser` | ✅ on | Retries with playwright-stealth JS-layer patches. Triggered by: bot challenge, HTTP 403, timeout |
| `patchright_load` | ✅ on | Retries with CDP-patched Chromium (binary-level, invisible to PerimeterX/DataDome). Triggered by: bot challenge, HTTP 403. Requires `patchright` package |
| `flaresolverr` | ✅ on | Obtains `cf_clearance` cookie from a FlareSolverr sidecar. Triggered by: Cloudflare detection. Requires `flaresolverr_url` config key |
| `camoufox_load` | ✅ on | Retries with patched Firefox engine (distinct TLS/HTTP2 fingerprint from Chromium). Always tried if still paywalled. Requires `camoufox` package |
| `ua_cycling` | ✅ on | Retries with next configured user agent (requires `user_agents.cycle: true`) |
| `header_tricks` | ✅ on | Retries with Googlebot UA, Google referer, and X-Forwarded-For header |
| `google_news` | ✅ on | Retries with Google News referer and Googlebot UA |
| `dom_ad_cleanup` | ✅ on | Removes residual ad elements from the DOM (Google Ads, DFP slots, Taboola, tracking pixels) |
| `image_dedup` | ✅ on | Collapses `<picture>` and `srcset` responsive images to a single URL ≤ 1200px wide |
| `content_extraction` | ✅ on | Last-resort: uses trafilatura to extract the article body if still paywalled |
| `archive_fallback` | ✅ on | Queries Wayback Machine then archive.today for an archived copy |
| `asset_inlining` | ✅ on | Inlines CSS, images, fonts, and scripts into a single self-contained HTML file using monolith |

{: .note }
`page_load` must always be present. `asset_inlining`, if included, must be last.

---

## FlareSolverr Integration

FlareSolverr is an optional Docker sidecar that solves Cloudflare IUAM challenges. To enable:

```yaml
# config.yaml
flaresolverr_url: "http://localhost:8191/v1"
```

Or set the `FLARESOLVERR_URL` environment variable. The `flaresolverr` pipeline step is a complete no-op if neither is configured.

**Docker Compose example:**

```yaml
services:
  archiveinator:
    image: ghcr.io/p0rkchop/archiveinator:latest
    ports: ["8080:8080"]
    volumes: ["archive-data:/data"]
    environment:
      - FLARESOLVERR_URL=http://flaresolverr:8191/v1
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    environment:
      - LOG_LEVEL=info
```

---

## User Agent Cycling

When `user_agents.cycle` is `true`, archiveinator will cycle through enabled user agents when a paywall is detected. Successful agent/domain pairs are cached so future runs on the same domain start with the known-good UA.

The UA cache is stored at:

| Platform | Cache Path |
|:---------|:-----------|
| macOS | `~/Library/Application Support/archiveinator/ua_cache.yaml` |
| Linux | `~/.config/archiveinator/ua_cache.yaml` |

### Enabling UA Cycling

```yaml
user_agents:
  cycle: true
  agents:
    - name: chrome_desktop
      enabled: true
      ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
    - name: googlebot
      enabled: true
      ua: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
```

---

## Web UI Configuration

When using the [Web UI](web-ui/), per-user configuration is stored in the SQLite database and managed through the Settings page. The YAML config file is only used by the CLI. Site profiles can override settings per-domain (user agent, timeout, stealth mode, pipeline steps).
