from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import typer

from archiveinator import console
from archiveinator.config import load as load_config

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
    from archiveinator.pipeline import ArchiveContext
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

    # --- Image deduplication (optional) ---
    if "image_dedup" in config.active_pipeline_steps():
        from archiveinator.steps.image_dedup import run as image_dedup_run

        asyncio.run(image_dedup_run(ctx))

    # --- Asset inlining (optional — degrades to partial save on failure) ---
    is_partial = False
    if "asset_inlining" in config.active_pipeline_steps():
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
