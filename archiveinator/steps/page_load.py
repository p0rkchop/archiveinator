from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from playwright.async_api import (
    Error as PlaywrightError,
)
from playwright.async_api import (
    Page,
    Request,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeout,
)

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


async def _wait_for_same_origin_network_idle(
    page: Page, target_origin: str, timeout_ms: int, idle_ms: int = 500
) -> None:
    """Wait until no same-origin requests are active for at least `idle_ms`.

    Same-origin is determined by comparing the request URL's origin (scheme+host+port)
    with `target_origin`. Requests whose origin does not match are ignored.

    Raises `TimeoutError` if the condition isn't met within `timeout_ms`.
    """
    active_same_origin: set[Request] = set()
    idle_timer: asyncio.Task[None] | None = None
    idle_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _origin(url: str) -> str:
        """Return scheme://host:port for url, or empty string if url cannot be parsed."""
        try:
            parsed = urlparse(url)
            if not parsed.hostname:
                return ""
            # Default ports for scheme
            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme == "https" else 80
            return f"{parsed.scheme}://{parsed.hostname}:{port}"
        except Exception:
            return ""

    def on_request(request: Request) -> None:
        nonlocal idle_timer
        if _origin(request.url) == target_origin:
            active_same_origin.add(request)
            if idle_timer is not None:
                idle_timer.cancel()
                idle_timer = None

    def on_request_done(request: Request) -> None:
        nonlocal idle_timer
        if request in active_same_origin:
            active_same_origin.remove(request)
            if not active_same_origin and idle_timer is None:
                # Start idle timer
                idle_timer = loop.create_task(asyncio.sleep(idle_ms / 1000.0))
                idle_timer.add_done_callback(lambda _: idle_event.set())

    page.on("request", on_request)
    page.on("requestfinished", on_request_done)
    page.on("requestfailed", on_request_done)

    try:
        await asyncio.wait_for(idle_event.wait(), timeout=timeout_ms / 1000.0)
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("requestfinished", on_request_done)
        page.remove_listener("requestfailed", on_request_done)
        if idle_timer is not None:
            idle_timer.cancel()


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
                # Log cookie domains for debugging
                domains: dict[str, int] = {}
                for c in ctx.cookies:
                    domain = c.get("domain", c.get("url", "unknown"))
                    domains[domain] = domains.get(domain, 0) + 1
                domain_summary = ", ".join(f"{d}:{n}" for d, n in sorted(domains.items()))
                console.step(f"Adding {len(ctx.cookies)} cookie(s) for domains: {domain_summary}")

                try:
                    await browser_context.add_cookies(ctx.cookies)  # type: ignore[arg-type]
                    console.step(f"Successfully added {len(ctx.cookies)} cookie(s)")
                except Exception as e:
                    console.warning(f"Failed to add cookies: {e}")
                    # Continue without cookies; authentication may fail
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

            loop = asyncio.get_event_loop()
            start = loop.time()
            try:
                response = await page.goto(
                    ctx.url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
            except PlaywrightError as exc:
                if isinstance(exc, PlaywrightTimeout):
                    raise PageLoadError(f"Timed out loading {ctx.url}") from exc
                else:
                    raise PageLoadError(f"Playwright error loading {ctx.url}: {exc}") from exc

            if response is None:
                raise PageLoadError(f"No response received for {ctx.url}")

            # Determine origin for same-origin network idle check
            target_url = response.url or ctx.url
            parsed = urlparse(target_url)
            if parsed.hostname:
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                target_origin = f"{parsed.scheme}://{parsed.hostname}:{port}"
            else:
                target_origin = ""

            # Wait for same-origin network idle with remaining timeout
            elapsed_ms = int((loop.time() - start) * 1000)
            remaining_ms = max(timeout_ms - elapsed_ms, 100)  # at least 100ms

            if target_origin:
                try:
                    await _wait_for_same_origin_network_idle(
                        page, target_origin, remaining_ms, idle_ms=500
                    )
                except TimeoutError:
                    console.warning(
                        "Same-origin network idle timed out, proceeding with current page state"
                    )
            else:
                console.debug("No hostname in URL, skipping same-origin network idle wait")

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
