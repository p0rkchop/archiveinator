from __future__ import annotations

from playwright.async_api import Page

from archiveinator import console

STEP = "dom_cleanup"

# Hostnames of known analytics, tracking, and ad-tech services.
# Used to identify and remove scripts that dynamically inject external resources
# at runtime — these cannot be intercepted by monolith's static HTML processing.
_TRACKER_HOSTS: list[str] = [
    "googletagmanager.com",
    "google-analytics.com",
    "googleadservices.com",
    "googlesyndication.com",
    "doubleclick.net",
    "parsely.com",
    "fontawesome.com",
    "stats.wp.com",
    "htlbid.com",
    "tagconcierge.com",
    "scorecardresearch.com",
    "taboola.com",
    "outbrain.com",
    "moatads.com",
    "krxd.net",
]

# CSS selectors targeting known ad/tracking elements.
# Ordered from most specific to most general to avoid false positives.
_AD_SELECTORS: list[str] = [
    # Google ads
    "ins.adsbygoogle",
    "[id^='google_ads']",
    "[id*='google_ads_iframe']",
    ".adsbygoogle",
    # Generic ad slots
    "[class*='ad-unit']",
    "[class*='ad-slot']",
    "[class*='ad-banner']",
    "[class*='ad-container']",
    "[class*='ad-wrapper']",
    "[class*='advert']",
    "[class*='advertisement']",
    "[data-ad]",
    "[data-advertisement]",
    "[data-ad-unit]",
    "[data-ad-slot]",
    # Sponsored / promoted content
    "[class*='sponsored']",
    "[class*='promoted']",
    "[class*='native-ad']",
    # Common ad network wrappers
    ".dfp-ad",
    ".dfp-slot",
    "[id*='dfp-ad']",
    # Outbrain / Taboola widgets
    "[data-widget-id*='outbrain']",
    ".ob-widget",
    ".trc_rbox",
    "[id*='taboola']",
    "[class*='taboola']",
    # Sticky / floating ad containers
    "[class*='sticky-ad']",
    "[class*='floating-ad']",
    "[id*='sticky-ad']",
    # Tracking pixels (1x1 images)
    "img[width='1'][height='1']",
    "img[src*='doubleclick']",
    "img[src*='facebook.com/tr']",
    "img[src*='scorecardresearch']",
]

_JS_REMOVE = """
(selectors) => {
    let count = 0;
    for (const sel of selectors) {
        try {
            for (const el of document.querySelectorAll(sel)) {
                el.remove();
                count++;
            }
        } catch (e) {
            // Ignore invalid selectors
        }
    }
    return count;
}
"""

# Removes resources that monolith cannot inline:
#
# 1. <link href="//..."> — protocol-relative URLs lack an explicit scheme, so
#    monolith cannot fetch and embed them. They're always third-party hints
#    (dns-prefetch, preconnect, stylesheet) with no content value for archives.
#
# 2. <script src="//..."> or <script src="https://tracker.com/..."> —
#    external script loaders that monolith cannot inline.
#
# 3. Inline <script> blocks whose content references tracker hostnames —
#    these dynamically inject external requests at runtime, after the static
#    HTML has been processed by monolith.
_JS_STRIP_EXTERNAL = """
(trackerHosts) => {
    let count = 0;

    // Remove <link> tags with protocol-relative hrefs
    for (const el of document.querySelectorAll('link[href^="//"]')) {
        el.remove();
        count++;
    }

    // Remove <script> tags with protocol-relative or tracker src
    for (const el of document.querySelectorAll('script[src]')) {
        const src = el.getAttribute('src') || '';
        if (src.startsWith('//') || trackerHosts.some(h => src.includes(h))) {
            el.remove();
            count++;
        }
    }

    // Remove inline <script> blocks that inject tracker resources at runtime
    for (const el of document.querySelectorAll('script:not([src])')) {
        const content = el.textContent || '';
        if (trackerHosts.some(h => content.includes(h))) {
            el.remove();
            count++;
        }
    }

    return count;
}
"""


async def apply(page: Page) -> int:
    """
    Remove ad/tracking DOM elements from the live page.
    Returns the number of elements removed.
    Must be called after page.goto() and before page.content().
    """
    removed: int = await page.evaluate(_JS_REMOVE, _AD_SELECTORS)
    removed += await page.evaluate(_JS_STRIP_EXTERNAL, _TRACKER_HOSTS)
    console.step(f"DOM cleanup: removed {removed} ad/tracker element(s)")
    return removed
