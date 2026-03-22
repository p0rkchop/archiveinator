from __future__ import annotations

from playwright.async_api import Page

STEP = "paywall_detection"

# HTTP statuses that commonly indicate a paywall / access restriction.
# Note: most paywalls return 200 with gated content, so DOM checks matter more.
_PAYWALL_HTTP_STATUSES: frozenset[int] = frozenset({401, 402, 403, 429})

# CSS selectors for known bot-challenge pages.
# These services return HTTP 200 with a challenge page, so status-code detection
# doesn't catch them — we need to identify them by DOM structure.
_BOT_CHALLENGE_SELECTORS: list[str] = [
    # PerimeterX (used by Bloomberg, others)
    "#px-captcha",
    "#px-loader",
    "[id^='px-']",
    # Cloudflare challenge
    "#challenge-form",
    ".cf-browser-verification",
    "#cf-content",
    "[data-ray]",
    # Akamai Bot Manager
    "#ak_bmsc",
    # DataDome
    "#datadome-captcha",
    # Generic challenge patterns
    "#captcha-container",
    "#robot-check",
    ".bot-check",
    "[id*='captcha'][id*='challenge']",
]

# Page title substrings that indicate a bot challenge or access denial.
# Checked case-insensitively against the document title.
_BOT_CHALLENGE_TITLE_PATTERNS: list[str] = [
    "are you a robot",
    "just a moment",
    "attention required",
    "access denied",
    "ddos protection",
    "browser check",
    "security check",
    "please verify",
    "robot check",
    "human verification",
]

# CSS selectors for known paywall / subscription-wall elements.
_PAYWALL_SELECTORS: list[str] = [
    # Piano / TinyPass (widely used by news publishers)
    ".tp-modal",
    "#tp-container",
    ".tp-backdrop",
    "#piano-inline",
    ".piano-offer",
    # Generic paywall class/id patterns
    ".paywall",
    "#paywall",
    "[class*='paywall']",
    "[id*='paywall']",
    ".subscription-wall",
    ".sub-wall",
    # Metered access overlays
    ".meter-wall",
    ".meter-paywall",
    ".article-paywall",
    ".article__paywall",
    # Publisher-specific
    ".nyt-meter-bar",
    ".js-sub-prompt",
    ".dynamic-paywall-prompt",
    ".subscription-prompt",
    ".paid-post",
    "[class*='paid-post']",
    # Content gate / article gate
    ".content-gate",
    ".article-gate",
    "[class*='content-gate']",
    # Subscriber-only indicators
    ".subscriber-only",
    "[class*='subscriber-only']",
    # Blurred / obscured content
    ".article--blurred",
    "[class*='article--blurred']",
    # Regwall (registration walls)
    ".regwall",
    "[class*='regwall']",
]

# Minimum number of words expected in a real article body.
# Pages with fewer words are likely showing a teaser / gated stub.
_MIN_WORD_COUNT = 150

_JS_DETECT_SELECTOR = """
(selectors) => {
    for (const sel of selectors) {
        try {
            if (document.querySelector(sel)) return sel;
        } catch (e) {}
    }
    return null;
}
"""

_JS_DETECT_TITLE = """
(patterns) => {
    const title = (document.title || '').toLowerCase();
    for (const p of patterns) {
        if (title.includes(p)) return title;
    }
    return null;
}
"""

_JS_WORD_COUNT = """
() => {
    const body = document.body;
    if (!body) return 0;
    const text = (body.innerText || body.textContent || '').trim();
    return text ? text.split(/\\s+/).length : 0;
}
"""


async def detect(page: Page, http_status: int) -> str | None:
    """Detect whether the loaded page is paywalled or a bot challenge.

    Returns a human-readable reason string if blocked, or None if not.
    Checks (in order):
      1. Unusual HTTP status codes
      2. Bot challenge DOM selectors (PerimeterX, Cloudflare, etc.)
      3. Bot challenge page title patterns
      4. Known paywall DOM selectors
      5. Suspiciously low word count
    """
    if http_status in _PAYWALL_HTTP_STATUSES:
        return f"HTTP {http_status}"

    bot_selector: str | None = await page.evaluate(_JS_DETECT_SELECTOR, _BOT_CHALLENGE_SELECTORS)
    if bot_selector:
        return f"bot challenge page (selector: {bot_selector})"

    bot_title: str | None = await page.evaluate(_JS_DETECT_TITLE, _BOT_CHALLENGE_TITLE_PATTERNS)
    if bot_title:
        return f"bot challenge page (title: {bot_title!r})"

    matched: str | None = await page.evaluate(_JS_DETECT_SELECTOR, _PAYWALL_SELECTORS)
    if matched:
        return f"DOM selector matched: {matched}"

    word_count: int = await page.evaluate(_JS_WORD_COUNT)
    if 0 < word_count < _MIN_WORD_COUNT:
        return f"low word count ({word_count})"

    return None
