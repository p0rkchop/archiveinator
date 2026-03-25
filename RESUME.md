# TDD Resume State
updated: 2026-03-25 11:00 UTC
session_branch: tdd/session-2026-03-24-2
current_paywall_type: complete (all types swept)
sites_passed_this_session:
  # Piano
  - NPR (piano, 3897 words) [prior session]
  - Boston Globe (piano, 1654 words) [prior session]
  - National Post Canada (piano, 1862 words) [prior session]
  - Pittsburgh Post-Gazette (piano, 1885 words)
  - Richmond Times-Dispatch (piano, 2696 words)
  - Omaha World-Herald (piano, 3273 words)
  - Toronto Star (piano, 4857 words)
  # Soft
  - Smithsonian Magazine (soft, 1223 words) [prior session]
  - Business Insider (soft, 462 words) [prior session]
  - The Guardian (soft, 1217 words)
  - Mother Jones (soft, 3277 words)
  - The Nation (soft, 342 words)
  - Jacobin (soft, 2391 words)
  - Politico (soft, 1051 words)
  - Fortune (soft, 765 words)
  - Common Dreams (soft, 1202 words)
  # Metered
  - LA Times (metered, 836 words) [prior session]
  - Dallas Morning News (metered, 1283 words)
  - Tampa Bay Times (metered, 1427 words)
  - Cleveland Plain Dealer (metered, 942 words)
  - NJ.com (metered, 929 words)
  - Scientific American (metered, 3977 words)
  # PerimeterX
  - Deadline (perimeter-x, 1518 words) [prior session]
  - Billboard (perimeter-x, 512 words) [prior session]
  - Rolling Stone (perimeter-x, 1236 words) [prior session]
  - Pitchfork (perimeter-x, 1323 words)
  - NME (perimeter-x, 787 words)
  - Hollywood Reporter (perimeter-x, 602 words)
  - MarketWatch (perimeter-x, 468 words)
  # Cloudflare
  - Axios (cloudflare, 901 words)
  - Inc (cloudflare, passed)
  - Fast Company (cloudflare, passed)
  - Globe and Mail Canada (cloudflare, passed)
  - New Scientist (cloudflare, passed)
  # Hard paywall
  - Wall Street Journal (hard, 860 words)
  - The Atlantic (hard, 538 words)
  - The New Yorker (hard, 1440 words)
  - Wired (hard, 1517 words)
  - Foreign Policy (hard, 2179 words)
  - Foreign Affairs (hard, 1028 words)
  - National Review (hard, 851 words)
  - The Information (hard, 499 words)
  - Nature (hard, 1286 words)
  - Sports Illustrated (hard, 1841 words)
  - ESPN+ (hard, 7031 words)
  # Baseline (no paywall)
  - The Onion (none, 1251 words)
  - BBC News (none, 2098 words)
  - The Verge (none, 1974 words)
  - Ars Technica (none, 1842 words)
  - ProPublica (none, 6853 words)
  - The Intercept (none, 2097 words)
  - Vox (none, 2311 words)
  - Reason (none, 8545 words)
  - TechCrunch (none, 815 words)
  - CNET (none, 5382 words)
  - Salon (none, 2890 words)

sites_intractable:
  - New York Times: HTTP 403 server-side for all bypass; genuine subscription paywall
  - Portland Oregonian: HTTP 403 server-side; Advance Local bot blocking
  - The Hill: PerimeterX "Access denied" for all strategies
  - Bloomberg: PerimeterX + hard paywall; content_extraction gets only robot page (97 words)
  - Seeking Alpha: PerimeterX #px-captcha + hard paywall; 95 words extracted
  - Sydney Morning Herald: Cloudflare + hard paywall; HTTP 403 on all strategies, 34 words
  - The Economist: Stealth browser gets through but only 61 words extracted
  - Washington Post: net::ERR_HTTP2_PROTOCOL_ERROR — hard network-level bot block
  - MIT Technology Review: No output file produced (page load failure)

sites_partial_save:
  - Slate: RSS article was a crossword puzzle (low content); monolith partial. Article-dependent.
  - HuffPost: 3046 words but _partial suffix — monolith asset inlining timeout

sites_flaky:
  - Variety: content_extraction works but word count depends on article length
  - Seattle Times: content_extraction gets 128-163 words; metered paywall limits visible content

next_action: >
  All paywall type groups have been swept. 47 of 56 RSS-enabled sites pass.
  Remaining work:
  1. Investigate Slate/HuffPost partial saves (monolith asset inlining timeouts)
  2. Consider adding RSS feeds for remaining rss_feed_needed sites
  3. 9 intractable/flaky sites likely need fundamentally different approaches
     (e.g. actual subscription credentials, residential proxy, or accepting archive fallback)
