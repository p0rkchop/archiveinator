---
layout: default
title: Pipeline
nav_order: 6
---

# Pipeline

archiveinator processes each URL through a configurable pipeline — a sequence of steps that run in order to block ads, load the page, detect and bypass paywalls, clean the DOM, and produce a self-contained HTML archive.

---

## How the Pipeline Works

1. Steps run **sequentially** in the order defined in your config
2. Each step receives an `ArchiveContext` object and passes it to the next step
3. Some steps run **inside the browser** (marked below) — they operate on the live page before it's serialized
4. The full pipeline is customizable — enable or disable steps in `config.yaml` or the Web UI Settings page
5. Bypass steps stop as soon as the page becomes accessible

---

## Pipeline Steps (in order)

### 1. `network_ad_blocking`

**Runs before browser launch.** Intercepts network requests and blocks ads, trackers, and known malicious domains using EasyList and EasyPrivacy rule sets. Requests to blocked domains are never made, saving bandwidth and preventing tracking.

Default: **enabled**

---

### 2. `page_load`

Launches a headless Chromium browser via Playwright and loads the target URL. Waits for network idle before proceeding. All subsequent in-browser steps operate on the page loaded here.

Default: **enabled** (required)

---

### 3. `paywall_detection`

**Runs inside the browser.** Detects whether the loaded page is behind a paywall using three methods:

- **HTTP status** — 401, 402, 403, or 429
- **DOM selectors** — known paywall elements (Piano/TinyPass modals, `.paywall`, `.content-gate`, and 30+ others)
- **Word count** — suspiciously low (< 150 words) indicates a teaser stub

If a paywall is detected, subsequent bypass strategies are triggered.

Default: **enabled**

---

### 4. `js_overlay_removal`

**Runs inside the browser.** Removes paywall modal elements from the live page DOM and restores body scroll before the page is serialized. No reload required — fires while the browser is still open.

Default: **enabled**

---

### 5. `js_disabled`

Retries the page load with JavaScript disabled. Some client-side paywalls rely entirely on JavaScript to hide content — loading the page without JS reveals the full article.

Default: **enabled**

---

### 6. `stealth_browser`

Retries with [playwright-stealth](https://github.com/AtuboDad/playwright-stealth) anti-fingerprinting patches applied. Patches JS properties that automation detection tools probe (`navigator.webdriver`, `navigator.plugins`, canvas fingerprint, etc.). Effective against Cloudflare "Just a moment" challenges and basic DataDome checks.

Default: **enabled**

---

### 7. `patchright_load`

Retries using [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) — a fork of Playwright that patches the Chromium binary itself to remove Chrome DevTools Protocol (CDP) socket detection signatures. Unlike `stealth_browser` (which patches at the JS layer), Patchright removes CDP fingerprints at the binary level, making automation undetectable by **PerimeterX** and modern **DataDome** challenges.

Triggered by: bot challenge, PerimeterX, or DataDome detection.

Requires: `pip install patchright && python -m patchright install chromium`

Default: **enabled** (no-op if patchright is not installed)

---

### 8. `flaresolverr`

Contacts a running [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) instance to obtain a `cf_clearance` cookie that bypasses **Cloudflare IUAM** (I'm Under Attack Mode) and **Turnstile** challenges. The cookie is injected into the browser context and the page is reloaded.

FlareSolverr is a Docker sidecar — it must be running separately. This step is a complete no-op if no URL is configured.

Enable by setting in `config.yaml`:
```yaml
flaresolverr_url: "http://localhost:8191/v1"
```
Or set the `FLARESOLVERR_URL` environment variable.

Triggered by: Cloudflare detection.

Default: **enabled** (no-op unless `flaresolverr_url` is set)

---

### 9. `camoufox_load`

Retries using [Camoufox](https://github.com/daijro/camoufox) — a patched Firefox binary that applies anti-fingerprinting at the binary level across canvas, WebGL, fonts, TLS ClientHello, and HTTP/2 SETTINGS frames. Firefox has a fundamentally different engine fingerprint from Chromium; sites tuned against Chromium automation often let Firefox through.

`humanize=True` adds realistic mouse movement and interaction timing for behavioral analysis bypass.

Triggered by: any paywall still present after the Chromium-based strategies above.

Requires: `pip install camoufox && python -m camoufox fetch`

Default: **enabled** (no-op if camoufox is not installed)

---

### 10. `ua_cycling`

If the page is still paywalled, retries the page load with the next enabled user agent from your config. Requires `user_agents.cycle: true`. Successful agent/domain pairs are cached so future runs on the same domain start with the known-good UA.

Default: **enabled**

---

### 11. `header_tricks`

Retries with Googlebot user agent, `Referer: https://www.google.com/`, and `X-Forwarded-For: 66.249.66.1`. Many publishers allow Googlebot through paywalls to stay indexed.

Default: **enabled**

---

### 12. `google_news`

Retries with Googlebot UA and `Referer: https://news.google.com/`, simulating a Google News click-through. Works on publishers that whitelist Google News traffic.

Default: **enabled**

---

### 13. `dom_ad_cleanup`

**Runs inside the browser.** Removes residual ad elements from the DOM — Google Ads, DFP slots, Taboola widgets, Outbrain containers, tracking pixels, and other advertising DOM cruft.

Default: **enabled**

---

### 14. `image_dedup`

**Runs inside the browser.** Collapses `<picture>` elements and `srcset` attributes to a single image URL ≤ 1200px wide. This prevents responsive image duplication in the final archive.

Default: **enabled**

---

### 15. `content_extraction`

Last-resort fallback if the page is still paywalled after all bypass strategies. Uses [trafilatura](https://trafilatura.readthedocs.io/) to extract the article body from whatever HTML was retrieved. The archive is saved as a clean, readable document containing the article text.

Default: **enabled**

---

### 16. `archive_fallback`

If the page is still inaccessible, queries the [Wayback Machine](https://web.archive.org/) and then [archive.today](https://archive.today/) for an archived copy of the URL. The most recent snapshot is used if found.

Default: **enabled**

---

### 17. `asset_inlining`

**Must be last if included.** Uses [monolith](https://github.com/Y2Z/monolith) to inline all external assets (CSS, images, fonts, JS) into a single self-contained HTML file. The result is a single file viewable offline with no external dependencies.

Default: **enabled**

---

## Bypass Strategy Summary

| Strategy | Targets | Trigger |
|---|---|---|
| `js_disabled` | Client-side JS paywalls | paywall detected |
| `stealth_browser` | Cloudflare, basic DataDome | bot challenge |
| `patchright_load` | PerimeterX, DataDome (CDP detection) | bot challenge |
| `flaresolverr` | Cloudflare IUAM/Turnstile | cloudflare detection |
| `camoufox_load` | Any Chromium-aware bot protection | all bot challenges |
| `ua_cycling` | UA-based rate limiting | any paywall |
| `header_tricks` | Google-whitelisted publishers | any paywall |
| `google_news` | Google News whitelisted publishers | any paywall |
| `content_extraction` | All (text extraction fallback) | any paywall |
| `archive_fallback` | All (archived copy fallback) | any paywall |

---

## Customizing the Pipeline

### Via Config File

```yaml
pipeline:
  - step: network_ad_blocking
    enabled: true
  - step: page_load
    enabled: true
  - step: paywall_detection
    enabled: false   # disable paywall detection
  - step: asset_inlining
    enabled: true
```

### Via Web UI

Visit **Settings** in the web interface to toggle steps on/off. Per-domain overrides can be set through [Site Profiles](web-ui/site-profiles).

