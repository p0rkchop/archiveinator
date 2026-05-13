"""Stealth browser bypass for Cloudflare / DataDome challenge pages.

Uses playwright-stealth to apply anti-fingerprinting patches (navigator.webdriver,
canvas, WebGL, chrome.runtime, etc.) before page load.  Only triggered when the
initial page load detected a bot challenge.

Also injects custom init scripts to patch properties that playwright-stealth
does not cover: navigator.plugins, navigator.hardwareConcurrency,
navigator.deviceMemory, and window.chrome.
"""

from __future__ import annotations

from playwright.async_api import Page
from playwright_stealth import Stealth

from archiveinator import console

STEP = "stealth_browser"

_stealth = Stealth()


_FINGERPRINT_INIT_SCRIPT = """
// Spoof navigator properties that headless Chromium leaves at zero
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        // Real Chrome has 3-5 plugins (PDF Viewer, Chrome PDF Viewer, etc.)
        return { length: 5, 0: {}, 1: {}, 2: {}, 3: {}, 4: {} };
    },
});
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
});
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
});

// Ensure chrome.runtime exists (real Chrome always has it)
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {};
}

// Patch permissions API — headless mode sometimes reports denied for everything
if (navigator.permissions && navigator.permissions.query) {
    const _originalQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (params) => {
        if (params.name === 'notifications') {
            return Promise.resolve({ state: 'prompt', onchange: null });
        }
        return _originalQuery(params);
    };
}
"""


async def apply(page: Page) -> None:
    """Apply stealth evasions to a Playwright page before navigation."""
    console.debug("Applying stealth anti-fingerprinting patches")
    await page.add_init_script(_FINGERPRINT_INIT_SCRIPT)
    await _stealth.apply_stealth_async(page)
