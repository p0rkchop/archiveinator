"""Patchright-based page load for PerimeterX and DataDome bypass.

Patchright is a drop-in fork of Playwright that patches the Chromium binary
itself to remove Chrome DevTools Protocol (CDP) socket detection signatures.
playwright-stealth only patches at the JS layer — Patchright removes the CDP
fingerprint at the binary level, making it undetectable by PerimeterX and
modern DataDome checks.

Only invoked when a bot challenge (PerimeterX / DataDome) is detected and the
standard stealth_browser step has failed.
"""

from __future__ import annotations

import contextlib

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "patchright_load"


class PatchrightLoadError(Exception):
    pass


async def run(ctx: ArchiveContext) -> None:
    """Load page via Patchright (CDP-patched Chromium) for PerimeterX/DataDome bypass."""
    try:
        from patchright.async_api import async_playwright as async_patchright
    except ImportError:
        console.debug("patchright not installed, skipping")
        return

    ua = ctx.ua_override or ctx.config.active_user_agent()
    timeout_ms = ctx.config.timeout_seconds * 1000
    stealth = ctx.config.stealth

    console.step("Loading page via Patchright (CDP-patched Chromium)")

    try:
        async with async_patchright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            try:
                browser_context = await browser.new_context(
                    user_agent=ua,
                    extra_http_headers=ctx.extra_headers or {},
                    ignore_https_errors=True,
                    viewport={"width": stealth.viewport_width, "height": stealth.viewport_height},
                    locale=stealth.locale,
                    timezone_id=stealth.timezone,
                    color_scheme="light",
                    device_scale_factor=1,
                )
                if ctx.cookies:
                    try:
                        await browser_context.add_cookies(ctx.cookies)  # type: ignore[arg-type]
                    except Exception as e:
                        console.warning(f"Patchright: failed to add cookies: {e}")

                page = await browser_context.new_page()
                response = await page.goto(
                    ctx.url, wait_until="domcontentloaded", timeout=timeout_ms
                )

                if response is None:
                    raise PatchrightLoadError(f"No response received for {ctx.url}")

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

            finally:
                await browser.close()

    except PatchrightLoadError:
        raise
    except Exception as exc:
        raise PatchrightLoadError(f"Patchright load failed: {exc}") from exc
