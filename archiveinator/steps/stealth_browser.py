"""Stealth browser bypass for Cloudflare / DataDome challenge pages.

Uses playwright-stealth to apply anti-fingerprinting patches (navigator.webdriver,
canvas, WebGL, chrome.runtime, etc.) before page load.  Only triggered when the
initial page load detected a bot challenge.
"""

from __future__ import annotations

from playwright.async_api import Page
from playwright_stealth import Stealth

from archiveinator import console

STEP = "stealth_browser"

_stealth = Stealth()


async def apply(page: Page) -> None:
    """Apply stealth evasions to a Playwright page before navigation."""
    console.debug("Applying stealth anti-fingerprinting patches")
    await _stealth.apply_stealth_async(page)
