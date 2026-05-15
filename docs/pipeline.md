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

### 5. `ua_cycling`

If the page is still paywalled, retries the page load with the next enabled user agent from your config. Requires `user_agents.cycle: true`. Successful agent/domain pairs are cached so future runs on the same domain start with the known-good UA.

Default: **enabled**

---

### 6. `header_tricks`

Retries with Googlebot user agent, `Referer: https://www.google.com/`, and `X-Forwarded-For: 66.249.66.1`. Many publishers allow Googlebot through paywalls to stay indexed.

Default: **enabled**

---

### 7. `google_news`

Retries with Googlebot UA and `Referer: https://news.google.com/`, simulating a Google News click-through. Works on publishers that whitelist Google News traffic.

Default: **enabled**

---

### 8. `dom_ad_cleanup`

**Runs inside the browser.** Removes residual ad elements from the DOM — Google Ads, DFP slots, Taboola widgets, Outbrain containers, tracking pixels, and other advertising DOM cruft.

Default: **enabled**

---

### 9. `image_dedup`

**Runs inside the browser.** Collapses `<picture>` elements and `srcset` attributes to a single image URL ≤ 1200px wide. This prevents responsive image duplication in the final archive.

Default: **enabled**

---

### 10. `content_extraction`

Last-resort fallback if the page is still paywalled after all bypass strategies. Uses [trafilatura](https://trafilatura.readthedocs.io/) to extract the article body from whatever HTML was retrieved. The archive is saved as a clean, readable document containing the article text.

Default: **enabled**

---

### 11. `asset_inlining`

**Must be last if included.** Uses [monolith](https://github.com/Y2Z/monolith) to inline all external assets (CSS, images, fonts, JS) into a single self-contained HTML file. The result is a single file viewable offline with no external dependencies.

Default: **enabled**

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
