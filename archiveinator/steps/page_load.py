from __future__ import annotations

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "page_load"

# These statuses indicate access restrictions (paywall, bot detection, rate limiting).
# They are NOT raised as PageLoadError — instead they flow through to paywall
# detection so the bypass suite can attempt to recover.
_SOFT_BLOCK_STATUSES: frozenset[int] = frozenset({401, 402, 403, 429})

_SOFT_BLOCK_REASONS: dict[int, str] = {
    401: "authentication required",
    402: "payment required",
    403: "access denied — likely bot detection or subscription wall",
    429: "rate limited — too many requests",
}


class PageLoadError(Exception):
    pass


async def run(ctx: ArchiveContext) -> None:
    """Load the page with Playwright and populate ctx.page_html, page_title, final_url.

    Respects ctx.ua_override and ctx.extra_headers when set by bypass strategies.
    Runs paywall detection and JS overlay removal inline (before serializing) when
    the corresponding pipeline steps are enabled.
    """
    ua = ctx.ua_override or ctx.config.active_user_agent()
    timeout_ms = ctx.config.timeout_seconds * 1000
    active_steps = ctx.config.active_pipeline_steps()

    console.step(f"Loading page: {ctx.url}")
    console.debug(f"User-agent: {ua}")
    if ctx.extra_headers:
        console.debug(f"Extra headers: {list(ctx.extra_headers.keys())}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            browser_context = await browser.new_context(
                user_agent=ua,
                extra_http_headers=ctx.extra_headers,
            )
            if ctx.cookies:
                await browser_context.add_cookies(ctx.cookies)  # type: ignore[arg-type]
                console.debug(f"Added {len(ctx.cookies)} cookie(s)")
            page = await browser_context.new_page()

            # Apply stealth anti-fingerprinting if requested by bypass suite
            if ctx.use_stealth and "stealth_browser" in active_steps:
                from archiveinator.steps.stealth_browser import apply as stealth_apply

                await stealth_apply(page)

            # Wire in network-level ad blocking before navigation if enabled
            if "network_ad_blocking" in active_steps:
                from archiveinator.blocklist import load_engine
                from archiveinator.steps.ad_blocking import register_interceptor

                engine = load_engine()
                await register_interceptor(page, engine)

            try:
                response = await page.goto(
                    ctx.url,
                    wait_until="networkidle",
                    timeout=timeout_ms,
                )
            except PlaywrightError as exc:
                if isinstance(exc, PlaywrightTimeout):
                    console.warning("networkidle timed out, falling back to domcontentloaded")
                    try:
                        response = await page.goto(
                            ctx.url,
                            wait_until="domcontentloaded",
                            timeout=timeout_ms,
                        )
                    except PlaywrightTimeout as exc2:
                        raise PageLoadError(f"Timed out loading {ctx.url}") from exc2
                else:
                    raise PageLoadError(f"Playwright error loading {ctx.url}: {exc}") from exc

            if response is None:
                raise PageLoadError(f"No response received for {ctx.url}")

            if response.status >= 400 and response.status not in _SOFT_BLOCK_STATUSES:
                raise PageLoadError(f"HTTP {response.status} for {ctx.url}")

            if response.status in _SOFT_BLOCK_STATUSES:
                reason = _SOFT_BLOCK_REASONS.get(response.status, f"HTTP {response.status}")
                console.warning(f"HTTP {response.status}: {reason}")

            ctx.response_status = response.status

            # DOM ad cleanup — runs in live browser context before serializing
            if "dom_ad_cleanup" in active_steps:
                from archiveinator.steps.dom_cleanup import apply as dom_cleanup

                removed = await dom_cleanup(page)
                ctx.log(STEP, f"dom_cleanup removed {removed} element(s)")

            # Paywall detection — inline, while browser is still open
            if "paywall_detection" in active_steps:
                from archiveinator.steps.paywall import detect

                paywall_reason = await detect(page, response.status)
                if paywall_reason:
                    ctx.paywalled = True
                    ctx.paywall_reason = paywall_reason
                    console.debug(f"Paywall detected: {paywall_reason}")

                    # JS overlay removal — attempt to clear the wall in-page
                    if "js_overlay_removal" in active_steps:
                        from archiveinator.steps.js_overlay import remove

                        removed = await remove(page)
                        ctx.log(STEP, f"js_overlay removed {removed} element(s)")

                        # Re-detect after removal
                        reason_after = await detect(page, response.status)
                        if reason_after is None:
                            ctx.paywalled = False
                            ctx.paywall_reason = None
                            ctx.bypass_method = "js_overlay_removal"
                            console.step("Paywall cleared by JS overlay removal")
                        else:
                            console.debug(f"Paywall persists after overlay removal: {reason_after}")
                else:
                    ctx.paywalled = False
                    ctx.paywall_reason = None

            ctx.page_title = await page.title()
            ctx.page_html = await page.content()
            ctx.final_url = page.url

            ctx.log(STEP, f"status={response.status} title={ctx.page_title!r} url={ctx.final_url}")
            console.step(f"Loaded: {ctx.page_title!r} ({ctx.final_url})")
        finally:
            await browser.close()
