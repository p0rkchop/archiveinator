from __future__ import annotations

from playwright.async_api import Page

from archiveinator import console

STEP = "js_overlay_removal"

# Selectors targeting paywall overlays and modal backdrops that JS renders
# on top of the article body. Ordered most-specific → most-general.
_OVERLAY_SELECTORS: list[str] = [
    # Piano / TinyPass overlays
    ".tp-modal",
    "#tp-container",
    ".tp-backdrop",
    ".piano-offer",
    "#piano-inline",
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
    // Restore scroll if overlays locked the body
    document.body.style.overflow = '';
    document.documentElement.style.overflow = '';
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
