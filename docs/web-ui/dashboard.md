---
layout: default
title: Dashboard
parent: Web UI
nav_order: 1
---

# Dashboard

The Dashboard is the main landing page after login. It provides a URL input for archiving, a real-time progress bar, and a summary of recent activity.

---

## Archive a Page

Enter a URL and click **Archive**. The page is processed through the [pipeline](../pipeline) with:

- Real-time progress streaming via WebSocket
- Step-by-step messages showing what the pipeline is doing
- Auto-detection of matching [site profiles](site-profiles) for the URL's domain
- Bypass strategy attempts shown as they happen

### Progress Bar

The progress bar fills as pipeline steps complete. Messages appear below showing:

- **Step starts/completions** — which pipeline step is running
- **Bypass attempts** — which strategy is being tried and whether it succeeded
- **Final result** — page title, duration, output file, paywall status

### Result

On completion, you'll see:

- Page title and final URL (after redirects)
- Duration and word count
- Whether a paywall was detected and if bypass was successful
- **Download** and **View** links for the archived HTML

---

## Quick Stats

Three stat cards show at-a-glance metrics:

| Stat | Description |
|:-----|:------------|
| **Total Archives** | All-time archive count |
| **Successful** | Archives that completed without errors |
| **Failed** | Archives that errored out |

---

## Recent Archives

The bottom of the dashboard lists your 5 most recent jobs with:

- Status badge (completed, failed, pending, running)
- URL or page title
- Timestamp

Click any job to see its full details including the step log and download link.

---

## Site Profile Indicator

Below the URL input, a profile indicator shows whether a matching [site profile](site-profiles) was found for the URL's domain:

- **"Using: My Profile (example.com)"** — a profile matches, cookies and settings will be applied
- **"No profile — using defaults"** — no profile found, global config will be used
- Link to create a new profile for the domain if none exists
