from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from typing import Any
from importlib import metadata
from pathlib import Path

import typer
from rich.console import Console as RichConsole
from rich.table import Table

from archiveinator import console
from archiveinator.config import load as load_config
from archiveinator.pipeline import ArchiveContext

# Get package version for help text
try:
    VERSION = metadata.version("archiveinator")
except metadata.PackageNotFoundError:
    VERSION = "unknown"

app = typer.Typer(
    help=f"archiveinator v{VERSION} — local web page archiver\n\nRun 'archiveinator COMMAND --help' for more details on a specific command.",
    no_args_is_help=True,
)

@app.callback(invoke_without_command=True)
def main_callback(version: bool = typer.Option(False, "--version", help="Show version and exit.")) -> None:
    """Run 'archiveinator COMMAND --help' for more details on a specific command."""
    if version:
        try:
            pkg_version = metadata.version("archiveinator")
        except metadata.PackageNotFoundError:
            pkg_version = "unknown"
        typer.echo(f"archiveinator v{pkg_version}")
        raise typer.Exit()

cache_app = typer.Typer(help="Manage the per-domain bypass strategy cache.")
app.add_typer(cache_app, name="cache")

_RETRY_DELAY_SECONDS = 2


def _abort(msg: str, exit_code: int = 1) -> None:
    console.error(msg)
    raise typer.Exit(code=exit_code)


def _validate_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        _abort(f"Invalid URL: {url!r}. Must start with http:// or https://")


def _load_cookies(file_path: str) -> list[dict[str, object]]:
    """Load cookies from JSON file, attempting conversion if needed.

    Supports:
    - Playwright format: list of cookie objects
    - Cookie-Editor format: {"cookies": [...]}
    - EditThisCookie format: array of cookie objects (same as Playwright)

    Returns a list of cookie dicts suitable for Playwright's add_cookies().
    Unknown fields are stripped; only Playwright-accepted fields are kept.
    """
    import json

    # Fields that Playwright's SetCookieParam accepts
    # https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies
    ALLOWED_FIELDS = {
        "name",
        "value",
        "url",
        "domain",
        "path",
        "expires",
        "httpOnly",
        "secure",
        "sameSite",
    }

    def _clean_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
        """Keep only fields Playwright understands."""
        return {k: v for k, v in cookie.items() if k in ALLOWED_FIELDS}

    try:
        with open(file_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Could not read or parse JSON: {e}") from e

    cookies: list[dict[str, Any]] = []

    # Already a list of cookie objects
    if isinstance(data, list):
        # Verify first element looks like a cookie
        if data and isinstance(data[0], dict) and "name" in data[0] and "value" in data[0]:
            cookies = data
        else:
            raise ValueError("JSON list does not contain cookie objects")

    # Cookie-Editor format: {"cookies": [...]}
    elif isinstance(data, dict) and "cookies" in data:
        cookies = data["cookies"]
        if not isinstance(cookies, list):
            raise ValueError("'cookies' field is not a list")

    else:
        # Unknown format
        raise ValueError(
            "Cookies file must be either:\n"
            "1. A JSON list of cookie objects (Playwright/EditThisCookie format), or\n"
            "2. A JSON object with a 'cookies' field (Cookie-Editor format)"
        )

    # Clean each cookie
    cleaned = [_clean_cookie(c) for c in cookies]
    return cleaned


def _try_strategy(
    ctx: ArchiveContext,
    strategy: str,
    active_steps: list[str],
    _reload: Callable[[], bool],
) -> bool:
    """Replay a single named bypass strategy.  Returns True if paywall cleared."""
    if strategy not in active_steps:
        return False

    if strategy == "stealth_browser":
        ctx.use_stealth = True
        ctx.extra_headers = {}
        if _reload():
            ctx.bypass_method = "stealth_browser"
            return True
        ctx.use_stealth = False
        return False

    if strategy == "ua_cycling":
        from archiveinator import ua_manager

        current_ua = ctx.ua_override or ctx.config.active_user_agent()
        next_ua = ua_manager.get_next_ua(ctx.url, ctx.config, current_ua)
        if next_ua:
            ctx.ua_override = next_ua
            ctx.extra_headers = {}
            if _reload():
                ctx.bypass_method = "ua_cycling"
                return True
        return False

    if strategy == "header_tricks":
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
            return True
        return False

    if strategy == "google_news":
        from archiveinator.steps.google_news import run as google_news_run

        asyncio.run(google_news_run(ctx))
        if _reload():
            ctx.bypass_method = "google_news"
            return True
        return False

    if strategy == "content_extraction":
        from archiveinator.steps.content_extraction import ContentExtractionError
        from archiveinator.steps.content_extraction import run as content_extract_run

        try:
            asyncio.run(content_extract_run(ctx))
            ctx.bypass_method = "content_extraction"
            return True
        except ContentExtractionError:
            return False

    if strategy == "archive_fallback":
        from archiveinator.steps.archive_fallback import check_archive_today, check_wayback

        snapshot_url = asyncio.run(check_wayback(ctx.url))
        if snapshot_url is None:
            snapshot_url = asyncio.run(check_archive_today(ctx.url))
        if snapshot_url:
            original_url = ctx.url
            ctx.url = snapshot_url
            if _reload():
                ctx.bypass_method = "archive_fallback"
                ctx.url = original_url  # Restore original for naming
                return True
            ctx.url = original_url
        return False

    return False


def _run_paywall_bypass(ctx: ArchiveContext, active_steps: list[str]) -> None:
    """Try bypass strategies in order until the paywall clears or all are exhausted.

    Checks the per-domain bypass cache first.  If a cached strategy exists,
    it is tried before the full suite.  Successful bypasses update the cache;
    exhaustion records a failure so demoted entries are eventually pruned.
    """
    from archiveinator import bypass_cache
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

    def _record_success(strategy: str, ua_name: str | None = None) -> None:
        bypass_cache.record_success(ctx.url, strategy, ua_name=ua_name)

    # --- Try cached strategy first ---
    cached = bypass_cache.lookup(ctx.url)
    if cached is not None:
        console.step(f"Bypass cache hit: trying cached strategy '{cached.strategy}'")
        if _try_strategy(ctx, cached.strategy, active_steps, _reload):
            _record_success(cached.strategy, ua_name=cached.ua_name)
            console.step(f"Paywall bypassed via cached strategy '{cached.strategy}'")
            return
        console.debug("Cached strategy failed, falling through to full suite")

    # --- Full strategy suite ---

    # Strategy 0: Stealth browser (for bot challenge pages and HTTP 403 blocks,
    # which often indicate bot detection at the CDN layer)
    _stealth_trigger = ctx.paywall_reason and (
        "bot challenge" in ctx.paywall_reason or "HTTP 403" in ctx.paywall_reason
    )
    if "stealth_browser" in active_steps and _stealth_trigger:
        console.step("Bypass: trying stealth browser (anti-fingerprinting)")
        ctx.use_stealth = True
        ctx.extra_headers = {}
        if _reload():
            ctx.bypass_method = "stealth_browser"
            _record_success("stealth_browser")
            console.step("Paywall bypassed via stealth browser")
            return
        ctx.use_stealth = False
        console.debug("Stealth browser did not clear the challenge")

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
                ua_name = None
                for agent in ctx.config.user_agents.agents:
                    if agent.ua == next_ua:
                        ua_manager.record_success(ctx.url, agent.name)
                        ua_name = agent.name
                        break
                _record_success("ua_cycling", ua_name=ua_name)
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
            _record_success("header_tricks")
            console.step("Paywall bypassed via header tricks")
            return

    # Strategy 3: Google News referral
    if "google_news" in active_steps and ctx.paywalled:
        console.step("Bypass: trying Google News referral")
        from archiveinator.steps.google_news import run as google_news_run

        asyncio.run(google_news_run(ctx))
        if _reload():
            ctx.bypass_method = "google_news"
            _record_success("google_news")
            console.step("Paywall bypassed via Google News referral")
            return

    # Strategy 4: Content extraction fallback (no reload — works on existing HTML)
    if "content_extraction" in active_steps and ctx.paywalled:
        console.step("Bypass: falling back to trafilatura content extraction")
        from archiveinator.steps.content_extraction import ContentExtractionError
        from archiveinator.steps.content_extraction import run as content_extract_run

        try:
            asyncio.run(content_extract_run(ctx))
            ctx.bypass_method = "content_extraction"
            _record_success("content_extraction")
            console.step("Content extracted via trafilatura")
            return
        except ContentExtractionError as e:
            console.warning(f"Content extraction failed: {e}")

    # Strategy 5: Archive service fallback (Wayback Machine, then archive.today)
    if "archive_fallback" in active_steps and ctx.paywalled:
        from archiveinator.steps.archive_fallback import check_archive_today, check_wayback

        console.step("Bypass: checking Wayback Machine for archived copy")
        snapshot_url = asyncio.run(check_wayback(ctx.url))
        if snapshot_url:
            original_url = ctx.url
            ctx.url = snapshot_url
            if _reload():
                ctx.bypass_method = "archive_fallback"
                ctx.url = original_url  # Restore original for file naming
                _record_success("archive_fallback")
                console.step("Content retrieved from Wayback Machine")
                return
            ctx.url = original_url

        if ctx.paywalled:
            console.step("Bypass: checking archive.today for archived copy")
            snapshot_url = asyncio.run(check_archive_today(ctx.url))
            if snapshot_url:
                original_url = ctx.url
                ctx.url = snapshot_url
                if _reload():
                    ctx.bypass_method = "archive_fallback"
                    ctx.url = original_url  # Restore original for file naming
                    _record_success("archive_fallback")
                    console.step("Content retrieved from archive.today")
                    return
                ctx.url = original_url

    # All strategies exhausted — record failure so cache can demote
    bypass_cache.record_failure(ctx.url)


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
    stealth: bool = typer.Option(
        False, "--stealth", help="Force stealth browser mode (anti-fingerprinting)"
    ),
    cookies_file: str | None = typer.Option(
        None,
        "--cookies-file",
        "-c",
        help="Path to JSON file containing cookies (Playwright format; Cookie-Editor and EditThisCookie exports are auto-detected)",
    ),
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
    if cookies_file:
        try:
            cookies = _load_cookies(cookies_file)
            ctx.cookies = cookies
            console.debug(f"Loaded {len(cookies)} cookie(s) from {cookies_file}")
        except ValueError as e:
            _abort(f"Failed to load cookies file: {e}")
    if stealth:
        ctx.use_stealth = True
        console.debug("Stealth mode forced via --stealth flag")
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
        console.warning(f"Paywall/block detected ({ctx.paywall_reason}) — trying bypass strategies")
        _run_paywall_bypass(ctx, active_steps)
        if ctx.paywalled:
            console.warning(
                "All bypass strategies exhausted — saving partial archive.\n"
                "  Tip: try --verbose to see each bypass attempt in detail."
            )

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
def setup(
    ignore_cert_errors: bool = typer.Option(
        False,
        "--ignore-cert-errors",
        help="Ignore SSL certificate errors during setup (use behind corporate proxies)",
    ),
) -> None:
    """Install dependencies: Playwright Chromium and monolith binary."""
    from archiveinator import setup_cmd
    from archiveinator.setup_cmd import SetupError

    try:
        setup_cmd.run(ignore_cert_errors=ignore_cert_errors)
    except SetupError as e:
        _abort(str(e))


@app.command(name="update-blocklists")
def update_blocklists(
    ignore_cert_errors: bool = typer.Option(
        False,
        "--ignore-cert-errors",
        help="Ignore SSL certificate errors during download (use behind corporate proxies)",
    ),
) -> None:
    """Download the latest EasyList and EasyPrivacy adblock rules."""
    from archiveinator.setup_cmd import _setup_blocklists

    _setup_blocklists(ignore_cert_errors=ignore_cert_errors)


# --- Cache subcommands ---


@cache_app.command(name="list")
def cache_list() -> None:
    """Show all cached bypass strategies."""
    from archiveinator.bypass_cache import list_entries

    entries = list_entries()
    if not entries:
        typer.echo("No cached entries.")
        return

    table = Table(title="Bypass Cache")
    table.add_column("Domain", style="cyan", no_wrap=True)
    table.add_column("Strategy", style="green", no_wrap=True)
    table.add_column("UA Name", no_wrap=True)
    table.add_column("Last Success", no_wrap=True)
    table.add_column("Attempts", justify="right")
    table.add_column("Successes", justify="right")
    table.add_column("Consecutive Failures", justify="right")

    for domain, entry in entries:
        table.add_row(
            domain,
            entry.strategy,
            entry.ua_name or "",
            entry.last_success or "",
            str(entry.attempts),
            str(entry.successes),
            str(entry.consecutive_failures),
        )

    rich_console = RichConsole(width=200)
    rich_console.print(table)


@cache_app.command(name="clear")
def cache_clear(
    domain: str | None = typer.Option(None, "--domain", "-d", help="Clear only this domain"),
) -> None:
    """Clear cached bypass entries (all or a specific domain)."""
    from archiveinator.bypass_cache import clear

    removed = clear(domain)
    if domain:
        if removed:
            typer.echo(f"Cleared cache entry for {domain}.")
        else:
            typer.echo(f"No cache entry found for {domain}.")
    else:
        typer.echo(f"Cleared {removed} cache entry(ies).")
