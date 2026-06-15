"""Camoufox-based page load for PerimeterX and Cloudflare bypass.

Camoufox is a patched Firefox binary that applies anti-fingerprinting at the
binary level — canvas noise, font enumeration, WebGL, TLS ClientHello, HTTP/2
SETTINGS frames, and OS-level fingerprint consistency. Unlike playwright-stealth
(which patches at the JS layer) or Patchright (which patches Chromium's CDP),
Camoufox uses a completely different browser engine (Firefox) with a much smaller
automated-traffic footprint in bot detection training data.

Sites that block all Chromium automation (PerimeterX, IUAM-hardened Cloudflare)
often let Firefox through because:
  - Firefox automation is far less common in scraper tooling
  - Firefox's engine signatures are distinct from Chromium at every layer
  - Bot detection training data skews heavily toward Chromium

Only invoked when bot challenge is still present after stealth_browser and
patchright_load have both failed.
"""

from __future__ import annotations

import contextlib

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "camoufox_load"


class CamoufoxLoadError(Exception):
    pass


async def run(ctx: ArchiveContext) -> None:
    """Load page via Camoufox (patched Firefox) for PerimeterX/Cloudflare bypass."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        console.debug("camoufox not installed, skipping")
        return

    ua = ctx.ua_override or ctx.config.active_user_agent()
    timeout_ms = ctx.config.timeout_seconds * 1000

    console.step("Loading page via Camoufox (patched Firefox)")

    try:
        async with AsyncCamoufox(headless=True, humanize=True) as browser:
            context = await browser.new_context(
                user_agent=ua,
                extra_http_headers=ctx.extra_headers or {},
                ignore_https_errors=True,
            )
            if ctx.cookies:
                try:
                    await context.add_cookies(ctx.cookies)  # type: ignore[arg-type]
                except Exception as e:
                    console.warning(f"Camoufox: failed to add cookies: {e}")

            page = await context.new_page()
            response = await page.goto(ctx.url, wait_until="domcontentloaded", timeout=timeout_ms)

            if response is None:
                raise CamoufoxLoadError(f"No response received for {ctx.url}")

            ctx.response_status = response.status
            ctx.final_url = page.url

            # Wait for network to settle
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=5000)

            ctx.page_html = await page.content()
            ctx.page_title = await page.title()

            # Run paywall detection on the result
            from archiveinator.steps.paywall import detect

            await detect(ctx, page)

    except CamoufoxLoadError:
        raise
    except Exception as exc:
        raise CamoufoxLoadError(f"Camoufox load failed: {exc}") from exc
