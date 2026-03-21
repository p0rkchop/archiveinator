from __future__ import annotations

from playwright.async_api import Page

from archiveinator import console

STEP = "dom_cleanup"

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


async def apply(page: Page) -> int:
    """
    Remove ad/tracking DOM elements from the live page.
    Returns the number of elements removed.
    Must be called after page.goto() and before page.content().
    """
    removed: int = await page.evaluate(_JS_REMOVE, _AD_SELECTORS)
    console.step(f"DOM cleanup: removed {removed} ad element(s)")
    return removed
