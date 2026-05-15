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
- **Word count** is suspiciously low (< 150 words), indicating a teaser stub rather than the full article

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

### 2. UA Cycling

Retries the page load with the next enabled user agent from your config.

- Requires `user_agents.cycle: true` in config
- Cycles through all enabled agents until one works or the list is exhausted
- **Successful agent/domain pairs are cached** — future runs on the same domain start with the known-good UA

---

### 3. Header Tricks

Retries the page load with:

- User-Agent: Googlebot
- Referer: `https://www.google.com/`
- X-Forwarded-For: `66.249.66.1`

Many publishers allow Googlebot through paywalls to stay indexed in search results.

---

### 4. Google News Referral

Retries the page load with:

- User-Agent: Googlebot
- Referer: `https://news.google.com/`

Simulates a click-through from Google News. Works on publishers that whitelist Google News traffic.

---

### 5. Content Extraction Fallback

If the page is **still** paywalled after all retries, [trafilatura](https://trafilatura.readthedocs.io/) extracts the article body from whatever HTML was retrieved.

The archive is saved as a clean, readable document containing the extracted article text — stripped of ads, navigation, and paywall elements.

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

## Partial Archives

If **all** strategies are exhausted without success, a partial archive of whatever HTML was retrieved is saved with `_partial` in the filename:

```
2026-03-21_14-30_example.com_article-title_partial.html
```

This ensures you have *some* content even when bypass fails — useful for pages that are paywalled through novel or undocumented methods.
