from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import typer

from archiveinator import console
from archiveinator.config import load as load_config
from archiveinator.pipeline import ArchiveContext

app = typer.Typer(
    help="archiveinator — local web page archiver",
    no_args_is_help=True,
)

_RETRY_DELAY_SECONDS = 2


def _abort(msg: str, exit_code: int = 1) -> None:
    console.error(msg)
    raise typer.Exit(code=exit_code)


def _validate_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        _abort(f"Invalid URL: {url!r}. Must start with http:// or https://")


def _run_paywall_bypass(ctx: ArchiveContext, active_steps: list[str]) -> None:
    """Try bypass strategies in order until the paywall clears or all are exhausted."""
    from archiveinator.steps.page_load import PageLoadError
    from archiveinator.steps.page_load import run as page_load_run

    def _reload() -> bool:
        """Re-run page_load and return True if paywall cleared."""
        try:
            asyncio.run(page_load_run(ctx))
        except PageLoadError as e:
            console.warning(f"Bypass page load failed: {e}")
            return False
        return not ctx.paywalled

    # Strategy 1: UA cycling
    if "ua_cycling" in active_steps:
        from archiveinator import ua_manager

        current_ua = ctx.ua_override or ctx.config.active_user_agent()
        next_ua = ua_manager.get_next_ua(ctx.url, ctx.config, current_ua)
        if next_ua:
            console.step("Bypass: trying UA cycling")
            ctx.ua_override = next_ua
            ctx.extra_headers = {}
            if _reload():
                ctx.bypass_method = "ua_cycling"
                # Record for future use
                for agent in ctx.config.user_agents.agents:
                    if agent.ua == next_ua:
                        ua_manager.record_success(ctx.url, agent.name)
                        break
                console.step("Paywall bypassed via UA cycling")
                return
        else:
            console.debug("UA cycling: no alternative UA available (cycle=false or single agent)")

    # Strategy 2: Header tricks (Googlebot UA + Google referer)
    if "header_tricks" in active_steps and ctx.paywalled:
        console.step("Bypass: trying header tricks (Googlebot UA + referer)")
        googlebot_ua: str | None = None
        for agent in ctx.config.user_agents.agents:
            if agent.name == "googlebot":
                googlebot_ua = agent.ua
                break
        ctx.ua_override = googlebot_ua or ctx.ua_override
        ctx.extra_headers = {
            "Referer": "https://www.google.com/",
            "X-Forwarded-For": "66.249.66.1",
        }
        if _reload():
            ctx.bypass_method = "header_tricks"
            console.step("Paywall bypassed via header tricks")
            return

    # Strategy 3: Google News referral
    if "google_news" in active_steps and ctx.paywalled:
        console.step("Bypass: trying Google News referral")
        from archiveinator.steps.google_news import run as google_news_run

        asyncio.run(google_news_run(ctx))
        if _reload():
            console.step("Paywall bypassed via Google News referral")
            return

    # Strategy 4: Content extraction fallback (no reload — works on existing HTML)
    if "content_extraction" in active_steps and ctx.paywalled:
        console.step("Bypass: falling back to trafilatura content extraction")
        from archiveinator.steps.content_extraction import ContentExtractionError
        from archiveinator.steps.content_extraction import run as content_extract_run

        try:
            asyncio.run(content_extract_run(ctx))
            console.step("Content extracted via trafilatura")
        except ContentExtractionError as e:
            console.warning(f"Content extraction failed: {e}")


@app.command()
def archive(
    url: str = typer.Argument(..., help="URL to archive"),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory (default: from config or CWD)"
    ),
    to_stdout: bool = typer.Option(
        False, "--stdout", "-s", help="Write archive to stdout; status messages go to stderr"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Archive a web page as a self-contained HTML file."""
    from archiveinator.naming import build_filename
    from archiveinator.steps.asset_inlining import AssetInliningError
    from archiveinator.steps.asset_inlining import run as inline_run
    from archiveinator.steps.page_load import PageLoadError
    from archiveinator.steps.page_load import run as page_load_run

    if to_stdout and output_dir is not None:
        _abort("--stdout and --output-dir are mutually exclusive")

    # When writing to stdout, redirect all status messages to stderr so they
    # don't interleave with the HTML output.
    console.configure(verbose=verbose, stderr=to_stdout)
    _validate_url(url)

    try:
        config = load_config()
    except Exception as e:
        _abort(f"Failed to load config: {e}")

    if output_dir is not None:
        config.output_dir = Path(output_dir)

    if not to_stdout and not config.output_dir.exists():
        _abort(f"Output directory does not exist: {config.output_dir}")

    console.debug(f"output_dir={config.output_dir}")
    console.debug(f"pipeline={config.active_pipeline_steps()}")

    ctx = ArchiveContext(url=url, config=config)
    active_steps = config.active_pipeline_steps()

    # --- Page load with one retry on failure ---
    last_page_error: PageLoadError | None = None
    for attempt in range(2):
        try:
            asyncio.run(page_load_run(ctx))
            last_page_error = None
            break
        except PageLoadError as e:
            last_page_error = e
            if attempt == 0:
                console.warning(f"Page load failed, retrying in {_RETRY_DELAY_SECONDS}s: {e}")
                time.sleep(_RETRY_DELAY_SECONDS)

    if last_page_error is not None:
        _abort(f"Failed to load page: {last_page_error}")

    # --- Paywall bypass suite ---
    if ctx.paywalled:
        console.warning(f"Paywall detected: {ctx.paywall_reason}")
        _run_paywall_bypass(ctx, active_steps)
        if ctx.paywalled:
            console.warning("All bypass strategies exhausted — archive may be incomplete")

    # --- Image deduplication (optional) ---
    if "image_dedup" in active_steps:
        from archiveinator.steps.image_dedup import run as image_dedup_run

        asyncio.run(image_dedup_run(ctx))

    # --- Asset inlining (optional — degrades to partial save on failure) ---
    is_partial = False
    if "asset_inlining" in active_steps:
        try:
            asyncio.run(inline_run(ctx))
        except AssetInliningError as e:
            console.warning(f"Asset inlining failed: {e}")
            is_partial = True
            ctx.is_partial = True

    # --- Output ---
    html = ctx.page_html or ""

    if to_stdout:
        sys.stdout.write(html)
        return

    title = ctx.page_title or ""
    filename = build_filename(url=ctx.final_url or url, title=title, partial=is_partial)
    output_path = config.output_dir / filename

    try:
        output_path.write_text(html, encoding="utf-8")
    except OSError as e:
        _abort(f"Failed to write output file: {e}")

    if is_partial:
        console.warning(f"Partial archive saved: {output_path}")
    else:
        console.success(f"Saved: {output_path}")


@app.command()
def setup() -> None:
    """Install dependencies: Playwright Chromium and monolith binary."""
    from archiveinator import setup_cmd
    from archiveinator.setup_cmd import SetupError

    try:
        setup_cmd.run()
    except SetupError as e:
        _abort(str(e))


@app.command(name="update-blocklists")
def update_blocklists() -> None:
    """Download the latest EasyList and EasyPrivacy adblock rules."""
    from archiveinator.setup_cmd import _setup_blocklists

    _setup_blocklists()
