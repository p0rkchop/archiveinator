from __future__ import annotations

import adblock
from playwright.async_api import Page, Request, Route

from archiveinator import console
from archiveinator.blocklist import should_block

STEP = "network_ad_blocking"

# Playwright resource types that map to adblock content types
_RESOURCE_TYPE_MAP = {
    "document": "document",
    "stylesheet": "stylesheet",
    "image": "image",
    "media": "media",
    "font": "font",
    "script": "script",
    "xhr": "xmlhttprequest",
    "fetch": "xmlhttprequest",
    "websocket": "websocket",
    "other": "other",
}


async def register_interceptor(page: Page, engine: adblock.Engine) -> None:
    """
    Register a Playwright route handler that blocks requests matched by the
    adblock engine. Must be called before page.goto().
    """

    async def handle_route(route: Route, request: Request) -> None:
        resource_type = _RESOURCE_TYPE_MAP.get(request.resource_type, "other")
        url = request.url
        source_url = page.url or ""

        if should_block(engine, url, source_url, resource_type):
            console.debug(f"Blocked: {url}")
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", handle_route)
    console.step("Ad blocking interceptor registered")
