from __future__ import annotations

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "page_load"


class PageLoadError(Exception):
    pass


async def run(ctx: ArchiveContext) -> None:
    """Load the page with Playwright and populate ctx.page_html, page_title, final_url."""
    ua = ctx.config.active_user_agent()
    timeout_ms = ctx.config.timeout_seconds * 1000
    active_steps = ctx.config.active_pipeline_steps()

    console.step(f"Loading page: {ctx.url}")
    console.debug(f"User-agent: {ua}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            browser_context = await browser.new_context(user_agent=ua)
            page = await browser_context.new_page()

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
            except PlaywrightTimeout as exc:
                raise PageLoadError(f"Timed out loading {ctx.url}") from exc

            if response is None:
                raise PageLoadError(f"No response received for {ctx.url}")

            if response.status >= 400:
                raise PageLoadError(f"HTTP {response.status} for {ctx.url}")

            # DOM ad cleanup — runs in live browser context before serializing
            if "dom_ad_cleanup" in active_steps:
                from archiveinator.steps.dom_cleanup import apply as dom_cleanup

                removed = await dom_cleanup(page)
                ctx.log(STEP, f"dom_cleanup removed {removed} element(s)")

            ctx.page_title = await page.title()
            ctx.page_html = await page.content()
            ctx.final_url = page.url

            ctx.log(STEP, f"status={response.status} title={ctx.page_title!r} url={ctx.final_url}")
            console.step(f"Loaded: {ctx.page_title!r} ({ctx.final_url})")
        finally:
            await browser.close()
