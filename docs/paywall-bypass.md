---
layout: default
title: Paywall Bypass
nav_order: 7
---

# Paywall Bypass

archiveinator automatically detects paywalled pages and works through a sequence of bypass strategies, stopping as soon as the page becomes accessible.

---

## Detection

A page is considered **paywalled** if any of the following are true:

- **HTTP status** is `401`, `402`, `403`, or `429`
- **DOM selectors** match known paywall elements:
  - Piano/TinyPass modals (`.tp-modal`, `.tp-backdrop`, `.piano-container`)
  - Generic paywall overlays (`.paywall`, `.content-gate`, `.metered-content`)
  - Subscription walls (`.subscribe-wall`, `.subscription-overlay`)
  - And 30+ additional publisher-specific selectors
- **Bot challenge page** — known challenge vendor selectors present:
  - PerimeterX: `#px-captcha`, `#px-loader`, `[id^='px-']`
  - Cloudflare: `#challenge-form`, `.cf-browser-verification`, `[data-ray]`
  - DataDome: `#datadome-captcha`, `[id*='datadome']`, `script[src*='datadome']`
  - Akamai: `#ak_bmsc`
- **Bot challenge title** — page title contains patterns like `"just a moment"`, `"are you a robot"`, `"access denied"`, `"ddos protection"`, etc.
- **Word count** is suspiciously low (< 150 words), indicating a teaser stub rather than the full article

Each check produces a **paywall reason string** that the bypass engine uses to choose which strategies to try. See [Bypass Decision Logic](#bypass-decision-logic) below.

---

## Bypass Decision Logic

The bypass engine reads the `paywall_reason` set by detection and uses it to select strategies. Not every strategy is tried for every block type — targeted strategies run first to avoid wasting time on approaches that can't work.

### Reason → Strategy Trigger Map

| Detection result | `paywall_reason` contains | Strategies triggered |
|:---|:---|:---|
| PerimeterX CAPTCHA | `"bot challenge"` | stealth_browser → **patchright_load** → camoufox_load → ua_cycling → header_tricks → google_news |
| Cloudflare challenge | `"bot challenge"` + `"cloudflare"` | stealth_browser → patchright_load → **flaresolverr** → camoufox_load → ua_cycling → header_tricks → google_news |
| DataDome CAPTCHA | `"bot challenge"` + `"datadome"` | stealth_browser → **patchright_load** → camoufox_load → ua_cycling → header_tricks → google_news |
| Subscription paywall | `"DOM selector matched"` | camoufox_load → ua_cycling → header_tricks → google_news → content_extraction → archive_fallback |
| HTTP 403 (soft) | `"HTTP 403"` | stealth_browser → patchright_load → camoufox_load → ua_cycling → header_tricks → google_news |
| HTTP 403 (hard block) | `"hard block"` | *(ua_cycling and content_extraction skipped)* → patchright_load → camoufox_load → header_tricks → google_news → archive_fallback |
| Timeout | `"timeout"` | stealth_browser → camoufox_load → ua_cycling → header_tricks → google_news |
| Low word count | `"low word count"` | camoufox_load → ua_cycling → header_tricks → google_news → content_extraction → archive_fallback |

**Bold** = the strategy specifically designed for that block type.

### Trigger Conditions (exact)

Each strategy checks a specific condition before running:

| Strategy | Fires when |
|:---------|:-----------|
| `stealth_browser` | `paywall_reason` contains `"bot challenge"`, `"HTTP 403"`, or `"timeout"` AND is not a hard block |
| `patchright_load` | `paywall_reason` contains `"bot challenge"`, `"perimeter"`, `"datadome"`, or `"HTTP 403"` |
| `flaresolverr` | `paywall_reason` contains `"cloudflare"` |
| `camoufox_load` | Page is still paywalled (always tried after above strategies) |
| `ua_cycling` | Page is still paywalled AND NOT a hard block AND `user_agents.cycle: true` |
| `header_tricks` | Page is still paywalled |
| `google_news` | Page is still paywalled |
| `content_extraction` | Page is still paywalled AND NOT a hard block |
| `archive_fallback` | Page is still paywalled |

### Hard Block vs Soft Block

A **hard block** is detected when the HTTP status is 403 AND the page has fewer than 100 words — indicating a server-side rejection with no useful content at all (e.g., a bare "Access Denied" page). Hard blocks skip `ua_cycling` and `content_extraction` since there's nothing to extract, and go straight to the archive fallback.

A **soft block** (subscription paywall) returns HTTP 200 with a partial article teaser and a DOM overlay or login gate.

### Bypass Cache

Before trying any strategy, the engine checks the **per-domain bypass cache**. If a previous run on the same domain succeeded with a specific strategy, that strategy is tried first — skipping strategies that have never worked for this domain.

On success, the winning strategy and UA (if applicable) are recorded. On total failure, the failure is recorded so stale cache entries are eventually pruned.

---

## Bypass Strategies (in order)

Strategies run sequentially. Each one is tried only if the page is still paywalled after the previous strategy.

### 1. JS Overlay Removal

**Runs inside the browser without reloading the page.**

Removes paywall modal elements from the live page DOM and restores body scroll before the page is serialized. This handles JS-injected overlays that appear after page load.

- No page reload required
- Fires while the browser is still open
- Targets Piano/TinyPass modals, generic overlays, and subscription gates

---

### 2. Stealth Browser

Retries with [playwright-stealth](https://github.com/AtuboDad/playwright-stealth) anti-fingerprinting patches applied — patches `navigator.webdriver`, `navigator.plugins`, canvas fingerprint, and other automation-detectable JS properties.

- Triggered by: bot challenge, HTTP 403, or timeout
- Effective against: Cloudflare "Just a moment", basic DataDome

---

### 3. Patchright (CDP-safe Chromium)

Retries using [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) — a Playwright fork that patches the Chromium binary to remove Chrome DevTools Protocol (CDP) socket detection signatures.

- Patches at the **binary level**, not the JS layer — bypasses detection that playwright-stealth cannot
- Triggered by: PerimeterX or DataDome bot challenge
- Effective against: PerimeterX, modern DataDome

---

### 4. FlareSolverr (Cloudflare IUAM solver)

Contacts a running [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) Docker sidecar to obtain a `cf_clearance` cookie, which is injected into the browser context for a subsequent reload.

- Targeted specifically at Cloudflare IUAM ("I'm Under Attack Mode") and Turnstile challenges
- No-op unless configured — set `flaresolverr_url: "http://localhost:8191/v1"` in config.yaml or `FLARESOLVERR_URL` env var
- Triggered by: Cloudflare detection

---

### 5. Camoufox (Firefox engine)

Retries using [Camoufox](https://github.com/daijro/camoufox) — a patched Firefox binary with binary-level anti-fingerprinting across canvas, WebGL, fonts, TLS ClientHello, and HTTP/2 SETTINGS frames.

- Uses a **completely different browser engine** (Firefox) — distinct from Chromium at every layer
- `humanize=True` adds realistic mouse movement and timing for behavioral analysis bypass
- Final browser-engine fallback — tried when all Chromium-based strategies fail

---

### 6. UA Cycling

Retries the page load with the next enabled user agent from your config.

- Requires `user_agents.cycle: true` in config
- Cycles through all enabled agents until one works or the list is exhausted
- **Successful agent/domain pairs are cached** — future runs on the same domain start with the known-good UA

---

### 7. Header Tricks

Retries the page load with:

- User-Agent: Googlebot
- Referer: `https://www.google.com/`
- X-Forwarded-For: `66.249.66.1`

Many publishers allow Googlebot through paywalls to stay indexed in search results.

---

### 8. Google News Referral

Retries the page load with:

- User-Agent: Googlebot
- Referer: `https://news.google.com/`

Simulates a click-through from Google News. Works on publishers that whitelist Google News traffic.

---

### 9. Content Extraction Fallback

If the page is **still** paywalled after all retries, [trafilatura](https://trafilatura.readthedocs.io/) extracts the article body from whatever HTML was retrieved.

The archive is saved as a clean, readable document containing the extracted article text — stripped of ads, navigation, and paywall elements.

---

### 10. Archive Service Fallback

Queries the [Wayback Machine](https://web.archive.org/) and then [archive.today](https://archive.today/) for an archived copy of the URL. The most recent snapshot is used if found.

---

## Bypass Cache

Successful bypasses are tracked per domain:

| What's cached | Purpose |
|:--------------|:--------|
| Winning user agent | Future runs on the same domain start with the known-good UA, skipping failed agents |
| Successful strategy | The last successful bypass approach is tried first on subsequent visits |

The cache is stored alongside the config file:

| Platform | Cache Path |
|:---------|:-----------|
| macOS | `~/Library/Application Support/archiveinator/ua_cache.yaml` |
| Linux | `~/.config/archiveinator/ua_cache.yaml` |

---

## Researching a New Paywalled Site

When a site's paywall isn't handled by the built-in strategies, use `archiveinator ladder` to quickly test header and referrer combinations before writing any code.

```bash
# Start the proxy
archiveinator ladder

# Test variations with curl — no browser spin-up, instant feedback
curl http://localhost:8181/https://example.com          # default Googlebot UA
curl http://localhost:8181/raw/https://example.com      # raw HTML
curl http://localhost:8181/api/https://example.com | jq '.body' | wc -w  # word count
```

Once you find a combination that works, create a rule file:

```yaml
# ~/.config/archiveinator/ladder-rules/example.yaml
domains:
  - example.com
rules:
  referer: "https://news.google.com/"
  user_agent: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
```

Restart `archiveinator ladder` to load the new rule, then verify with `curl`. When the approach is confirmed, encode it as a site profile in the Web UI (Settings → Site Profiles) using the same UA and referrer values — future archives of that domain will pick it up automatically.

---

## Partial Archives

If **all** strategies are exhausted without success, a partial archive of whatever HTML was retrieved is saved with `_partial` in the filename:

```
2026-03-21_14-30_example.com_article-title_partial.html
```

This ensures you have *some* content even when bypass fails — useful for pages that are paywalled through novel or undocumented methods.
