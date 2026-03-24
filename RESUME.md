# TDD Resume State
updated: 2026-03-24 (session 1, context limit)
session_branch: tdd/session-2026-03-24
current_paywall_type: piano
sites_passed_this_session: []
sites_intractable_this_session: []
sites_in_progress: []
infrastructure_completed_this_session:
  - Added rss_resolver.py (tests/qa/) — fetches latest article from RSS/Atom feed at test runtime
  - Updated test_real_urls.py to use resolve_site_url() for live article URLs
  - Added rss_feed to 12 sites in sites.yaml (verified working feeds)
  - Added rss_feed_needed:true to all other sites (84 sites) — skipped until feeds added
  - Updated conftest.py — skips rss_feed_needed sites by default; added --qa-site and --qa-include-rss-needed flags
  - Fixed reporter.py — exact CSS class token matching (was substring, caused NPR false positive)
  - Fixed paywall.py — added .tp-container class selector (was only #tp-container ID)
  - Fixed content_extraction.py — 50-word quality gate rejects challenge page extractions
  - All unit tests green (190 passed, 1 pre-existing blocklist failure unrelated to paywall)
next_action: >
  Start TDD loop on piano group. Sites with working RSS feeds in piano type:
    1. NPR (rss_feed_needed:true — add RSS feed first, e.g. https://feeds.npr.org/1001/rss.xml)
    2. Boston Globe (rss_feed: https://www.bostonglobe.com/arc/outboundfeeds/rss/?outputType=xml)
    3. National Post Canada (rss_feed: https://nationalpost.com/feed/)

  NPR does not yet have an rss_feed in sites.yaml (rss_feed_needed:true).
  Verify https://feeds.npr.org/1001/rss.xml returns real articles, then add it to sites.yaml.
  Then run: uv run pytest tests/qa/test_real_urls.py -m real_url --qa-site "NPR" -v
rss_enabled_sites:
  - The Hill (perimeter-x)
  - Smithsonian Magazine (soft)
  - Business Insider (soft)
  - New York Times (metered)
  - LA Times (metered)
  - Portland Oregonian (metered)
  - Boston Globe (piano)
  - National Post Canada (piano)
  - Variety (perimeter-x)
  - Deadline (perimeter-x)
  - Billboard (perimeter-x)
  - Rolling Stone (perimeter-x)
