from __future__ import annotations

from playwright.async_api import Page

from archiveinator import console

STEP = "js_overlay_removal"

# Selectors targeting paywall overlays and modal backdrops that JS renders
# on top of the article body. Ordered most-specific → most-general.
_OVERLAY_SELECTORS: list[str] = [
    # Piano / TinyPass overlays – explicit classes
    ".tp-modal",
    "#tp-container",
    ".tp-backdrop",
    ".piano-offer",
    "#piano-inline",
    # Catch-all for any element whose class contains "tp-" (TinyPass prefix)
    "[class*='tp-']",
    # Script tags that load Piano / TinyPass JS
    "script[src*='tinypass']",
    "script[src*='piano.io']",
    # Link tags referencing Piano stylesheets / resources
    "link[href*='piano']",
    # Generic paywall overlays
    ".paywall",
    "#paywall",
    "[class*='paywall']",
    ".subscription-wall",
    ".meter-wall",
    ".meter-paywall",
    ".article-paywall",
    ".article__paywall",
    ".content-gate",
    ".article-gate",
    "[class*='content-gate']",
    ".subscriber-only",
    "[class*='subscriber-only']",
    ".regwall",
    "[class*='regwall']",
    # Generic modal backdrops that block scroll
    ".modal-backdrop",
    ".modal-overlay",
    "[class*='modal-backdrop']",
    "[class*='modal-overlay']",
    # Cookie consent / GDPR / privacy banners
    ".cookie-banner",
    "#cookie-banner",
    ".cookie-consent",
    ".cookie-notice",
    ".gdpr-banner",
    ".cc-banner",
    ".privacy-consent",
    ".consent-banner",
    ".gdpr-cookie-banner",
    "[class*='cookie'][class*='banner']",
    "[id*='cookie'][id*='banner']",
    # Newsletter / subscription popups
    ".newsletter-popup",
    "#newsletter-popup",
    "[class*='newsletter'][class*='popup']",
    "[class*='newsletter'][class*='modal']",
    ".email-signup",
    ".signup-modal",
    ".subscribe-popup",
    # Age verification gates
    ".age-gate",
    "#age-verification",
    ".age-verification",
    ".birthday-wall",
    ".age-wall",
    # Continue reading / teaser prompts
    ".continue-reading",
    ".read-more-prompt",
    ".teaser-wall",
    ".partial-content",
    ".preview-wall",
    # Ad-block detection warnings
    ".adblock-warning",
    "#adblock-detected",
    ".please-disable-adblock",
    ".anti-adblock",
    # Site messages / notification bars
    ".site-message",
    ".site-notice",
    ".notification-bar",
    ".alert-banner",
    ".site-alert",
    # Generic overlay patterns (catch-alls)
    "[class*='overlay']",
    "[class*='popup']",
    "[class*='modal']",
]

_JS_REMOVE_OVERLAYS = """
(selectors) => {
    let count = 0;
    for (const sel of selectors) {
        try {
            for (const el of document.querySelectorAll(sel)) {
                el.remove();
                count++;
            }
        } catch (e) {}
    }
    // Restore scroll/position if overlays locked the body
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
    document.body.style.position = '';
    return count;
}
"""


async def remove(page: Page) -> int:
    """Remove JS-rendered paywall overlays from the live page.

    Restores body scroll in case the overlay locked it.
    Returns the number of elements removed.
    Must be called after page.goto() and before page.content().
    """
    removed: int = await page.evaluate(_JS_REMOVE_OVERLAYS, _OVERLAY_SELECTORS)
    console.step(f"JS overlay removal: removed {removed} element(s)")
    return removed
