# TDD Resume State
updated: 2026-03-24 18:30 UTC
session_branch: tdd/session-2026-03-24
current_paywall_type: perimeter-x
sites_passed_this_session:
  - NPR (piano, 3897 words)
  - Boston Globe (piano, 1654 words)
  - National Post Canada (piano, 1862 words)
  - Smithsonian Magazine (soft, 1223 words)
  - Business Insider (soft, 462 words)
  - LA Times (metered, 836 words)
  - Deadline (perimeter-x, 1518 words)
  - Billboard (perimeter-x, 512 words)
  - Rolling Stone (perimeter-x, 1236 words)
sites_intractable_this_session:
  - New York Times: HTTP 403 server-side for all bypass attempts; no content served to bots; genuine subscription paywall. Attempts: (1) full suite all 403, (2) stealth browser on 403 - still blocked. Intractable.
  - Portland Oregonian: Same as NYT — HTTP 403 server-side for all bypass strategies, Advance Local bot blocking. Intractable.
  - The Hill: PerimeterX "Access to this page has been denied" for all strategies, 47-word block page. Intractable with current playwright-stealth approach.
sites_in_progress:
  - Variety: content_extraction works (strategy cached) but today's RSS article is 103 words (< 300 threshold). Article is genuinely short, not a paywall failure. Will likely pass on a different day's article.
next_action: >
  Resume perimeter-x group. Variety may self-resolve with a longer RSS article.
  Consider testing The Hill with a fresh approach on next session.
  Then move to cloudflare group (The Hill is cloudflare-adjacent via PerimeterX).
  RSS-enabled sites remaining to test: None in cloudflare group (all rss_feed_needed).
  Consider adding RSS feeds for: Globe and Mail (Canada), New Scientist, etc.

infrastructure_changes_this_session:
  - Added rss_resolver.py: RSS/Atom feed resolver with session-level caching
  - Added rss_feed to 13 sites (including NPR verified at feeds.npr.org/1001/rss.xml)
  - Added rss_feed_needed:true to 84 sites — skipped until feeds added
  - Updated conftest: --qa-site, --qa-include-rss-needed flags; skip rss_feed_needed by default
  - Fixed reporter.py: exact CSS class token matching (was substring)
  - Fixed paywall.py: added .tp-container class selector
  - Fixed content_extraction.py: 50-word quality gate rejects challenge pages
  - Fixed asset_inlining.py: suppress external assets when bypass was used
  - Fixed cli.py: stealth_browser now triggers on HTTP 403 (in addition to bot challenge pages)

rss_enabled_sites:
  piano:
    - NPR: https://feeds.npr.org/1001/rss.xml ✓
    - Boston Globe: https://www.bostonglobe.com/arc/outboundfeeds/rss/?outputType=xml ✓
    - National Post Canada: https://nationalpost.com/feed/ ✓
  soft:
    - Smithsonian Magazine: https://www.smithsonianmag.com/rss/latest_articles/ ✓
    - Business Insider: https://feeds.businessinsider.com/custom/all ✓
  metered:
    - LA Times: https://www.latimes.com/rss2.0.xml ✓
    - NYT: https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml (intractable — HTTP 403)
    - Portland Oregonian: https://www.oregonlive.com/arc/outboundfeeds/rss/?outputType=xml (intractable — HTTP 403)
  perimeter-x:
    - Deadline: https://deadline.com/feed/ ✓
    - Billboard: https://www.billboard.com/feed/ ✓
    - Rolling Stone: https://www.rollingstone.com/feed/ ✓
    - The Hill: https://thehill.com/feed/ (intractable — PerimeterX block)
    - Variety: https://variety.com/feed/ (flaky — article length dependent)
