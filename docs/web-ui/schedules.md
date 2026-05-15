---
layout: default
title: Schedules
parent: Web UI
nav_order: 4
---

# Schedules

Set up recurring archives of specific URLs on cron schedules. Archiveinator uses APScheduler with cron triggers to run archives at the intervals you define.

---

## Creating a Schedule

1. Go to **Schedules** in the navigation bar
2. Click **New Schedule**
3. Fill in the details:

### Fields

| Field | Required | Description |
|:------|:---------|:------------|
| **URL** | Yes | The URL to archive on schedule |
| **Label** | No | Human-readable name for the schedule |
| **Cron Expression** | Yes | Standard 5-field cron: `minute hour day month weekday` |
| **Site Profile** | No | Profile to use for cookies/settings on the target domain |

---

## Cron Expression Presets

Quick-select buttons for common schedules:

| Preset | Cron Expression | Fires |
|:-------|:----------------|:------|
| Every 30 minutes | `*/30 * * * *` | On the half-hour, every hour |
| Hourly | `0 * * * *` | At the top of every hour |
| Every 6 hours | `0 */6 * * *` | At midnight, 6am, noon, 6pm |
| Daily | `0 9 * * *` | Every day at 9am |
| Weekdays | `0 9 * * 1-5` | Weekdays at 9am |
| Weekly | `0 9 * * 1` | Every Monday at 9am |

{: .note }
All times are in the server's local timezone.

---

## Managing Schedules

### Toggle On/Off

Enable or disable schedules without deleting them. Disabled schedules don't fire but keep their configuration.

### Run Now

Click **Run Now** on any schedule to trigger an immediate archive, regardless of the cron schedule. Useful for testing or one-off needs.

### Editing

You can change the URL, label, cron expression, or linked profile at any time. Changes take effect immediately.

### Deleting

Deleting a schedule removes it from the database. Existing archived files are **not** deleted.

---

## Server Restart Behavior

Schedules are stored in the SQLite database and restored on server startup. If the server is down when a schedule would have fired, it will fire at the next matching interval after the server comes back up.

---

## Monitoring

Each time a schedule fires, the resulting archive job appears in the job history. You can see:

- When each schedule last ran
- Whether the last run succeeded or failed
- A link to the archive job for detailed results
