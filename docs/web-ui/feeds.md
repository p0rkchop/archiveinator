---
layout: default
title: RSS Feeds
parent: Web UI
nav_order: 3
---

# RSS Feeds

Subscribe to RSS and Atom feeds to automatically archive new articles as they're published. Archiveinator polls feeds on a configurable interval and archives each new item with your linked site profile.

---

## Adding a Feed

1. Go to **Feeds** in the navigation bar
2. Click **Add Feed**
3. Enter the feed URL and optionally a label and check interval
4. Optionally link a [site profile](site-profiles) for authenticated archiving
5. Click **Add**

The feed is validated immediately — you'll see the feed title and item count before adding.

---

## How Feed Polling Works

1. APScheduler triggers a periodic check of all feeds
2. Each feed whose interval has elapsed is fetched with conditional GET (ETag/Last-Modified headers)
3. New items are compared against the `feed_items` table for deduplication
4. Each new item URL is submitted as an archive job
5. The job uses the feed's linked site profile (if set) for cookies and settings

### Check Intervals

The default check interval is **60 minutes**. You can set a custom interval per feed (in minutes). Shorter intervals mean more frequent polling.

---

## Feed Management

### Viewing Items

Click a feed to see all discovered items — shows:

- Article title and URL
- Publication date
- Whether it's been archived (with link to the job)

### Manual Check

Click **Check Now** on any feed to trigger an immediate poll, bypassing the interval timer.

### Deleting a Feed

Deleting a feed removes the feed record and all its associated items from the database. Archived HTML files are **not** deleted.

---

## Deduplication

Feed items are deduplicated by `(feed_id, url)`. If an item URL appears in the feed again (common with "Most Popular" or "Latest" feeds that shuffle items), it will not be re-archived.

---

## Conditional GET

Archiveinator sends `ETag` and `Last-Modified` headers from the previous successful fetch. If the feed server responds with `304 Not Modified`, no items are processed — saving bandwidth and respecting upstream rate limits.
