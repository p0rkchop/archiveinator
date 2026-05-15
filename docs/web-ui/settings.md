---
layout: default
title: Settings
parent: Web UI
nav_order: 5
---

# Settings

Configure your default pipeline, user agents, timeouts, and email notification preferences. These settings apply to all archives except where overridden by a [site profile](site-profiles).

---

## Pipeline Steps

Toggle each pipeline step on or off:

| Step | Description |
|:-----|:------------|
| `network_ad_blocking` | Block ad/tracker requests before they're made |
| `page_load` | Load the page in headless Chromium |
| `paywall_detection` | Detect if the page is behind a paywall |
| `js_overlay_removal` | Remove paywall modals from the live DOM |
| `ua_cycling` | Retry with next user agent (requires UA cycling enabled) |
| `header_tricks` | Retry with Googlebot UA and referer |
| `google_news` | Retry with Google News referer |
| `dom_ad_cleanup` | Remove residual ad elements from DOM |
| `image_dedup` | Collapse responsive images to single size |
| `content_extraction` | trafilatura extraction if still paywalled |
| `asset_inlining` | Inline all assets into self-contained HTML |

{: .note }
`page_load` is always enabled and cannot be toggled off. `asset_inlining` must be last if enabled.

See the [Pipeline](../pipeline) documentation for detailed explanations of each step.

---

## User Agents

Manage the list of user agents used for UA cycling:

- **Enable/disable** individual agents
- **Add custom agents** with a name and UA string
- **Toggle UA cycling** on/off globally

When UA cycling is enabled and a paywall is detected, archiveinator cycles through enabled agents until one works or the list is exhausted. Successful agent/domain pairs are cached.

---

## Timeout

Set the default page load timeout in seconds (default: 40). This can be overridden per-domain in [site profiles](site-profiles).

---

## Email Notifications

Configure email notifications for job completion:

| Setting | Description |
|:--------|:------------|
| **Email Address** | Where notifications are sent (defaults to registration email) |
| **Enable Notifications** | Toggle on/off |
| **RESEND_API_KEY** | Server-side environment variable — set by the instance admin |

When enabled, you'll receive an email after each archive job with:

- Job status (completed or failed)
- Page title and URL
- Duration and word count
- Paywall status and bypass method
- Link to download the archive

If `RESEND_API_KEY` is not set at the server level, email sending is silently skipped even if notifications are enabled on your account.

---

## Storage

Archived HTML files are saved to the server's data directory (`/data/output` in Docker, or the platform data directory locally). You can download them from the job detail page or the job history list.
