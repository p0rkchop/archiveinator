from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from pytest_httpserver import HTTPServer

from archiveinator.config import Config, PipelineStep
from archiveinator.naming import build_filename
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.asset_inlining import AssetInliningError
from archiveinator.steps.asset_inlining import run as inline_run
from archiveinator.steps.image_dedup import run as image_dedup_run
from archiveinator.steps.page_load import PageLoadError
from archiveinator.steps.page_load import run as page_load_run

# A realistic article page with ads mixed into real content
_ARTICLE_PAGE = """\
<!DOCTYPE html>
<html>
<head>
  <title>Scientists Discover New Species - Nature Weekly</title>
  <style>body { font-family: sans-serif; }</style>
</head>
<body>
  <header><h1>Nature Weekly</h1></header>

  <article>
    <h2>Scientists Discover Remarkable New Species in Amazon</h2>
    <p>Researchers announced the discovery of a previously unknown species of
    tree frog deep in the Amazon rainforest. The creature, distinguished by its
    vibrant blue markings, was found during a three-week expedition.</p>
    <p>The team, led by Dr. Elena Vasquez, described the find as extraordinary.</p>
  </article>

  <!-- Ad elements that should be stripped -->
  <ins class="adsbygoogle" data-ad-slot="1234567890" style="display:block"></ins>
  <div class="ad-banner"><p>ADVERTISEMENT</p></div>
  <div class="ad-unit" id="sidebar-ad">Buy stuff!</div>
  <img width="1" height="1" src="https://tracking.example.com/pixel.gif" alt="">
  <div class="sponsored">Sponsored content here</div>

  <footer><p>&copy; Nature Weekly</p></footer>
</body>
</html>
"""


def _monolith_passthrough(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    """Fake subprocess.run: copies input file to output file unchanged."""
    input_file = Path(cmd[1])
    output_idx = cmd.index("-o") + 1
    output_file = Path(cmd[output_idx])
    output_file.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
    return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")


def _setup_monolith_mock(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Patch monolith_bin and mock the subprocess call."""
    import archiveinator.steps.asset_inlining as ai_mod

    fake_bin = tmp_path / "monolith"
    fake_bin.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: fake_bin)
    monkeypatch.setattr(subprocess, "run", _monolith_passthrough)


def _test_config(timeout: int = 10, include_dom_cleanup: bool = False) -> Config:
    """Return a minimal Config suitable for testing."""
    config = Config()
    config.timeout_seconds = timeout
    steps = [
        PipelineStep(step="page_load", enabled=True),
        PipelineStep(step="image_dedup", enabled=True),
        PipelineStep(step="asset_inlining", enabled=True),
    ]
    if include_dom_cleanup:
        steps.insert(1, PipelineStep(step="dom_ad_cleanup", enabled=True))
    config.pipeline = steps
    return config


def _write_archive(ctx: ArchiveContext, output_dir: Path) -> Path:
    """Write the archive to disk, mirroring what the CLI does."""
    title = ctx.page_title or ""
    filename = build_filename(
        url=ctx.final_url or ctx.url,
        title=title,
        partial=ctx.is_partial,
    )
    output_path = output_dir / filename
    output_path.write_text(ctx.page_html or "", encoding="utf-8")
    return output_path


# --- Happy path ---


@pytest.mark.asyncio
async def test_full_pipeline_creates_output_file(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    config = _test_config()
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/article"), config=config)

    await page_load_run(ctx)
    await image_dedup_run(ctx)
    await inline_run(ctx)

    _write_archive(ctx, tmp_path)
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1


@pytest.mark.asyncio
async def test_full_pipeline_filename_format(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    config = _test_config()
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/article"), config=config)

    await page_load_run(ctx)
    await image_dedup_run(ctx)
    await inline_run(ctx)

    output_path = _write_archive(ctx, tmp_path)
    name = output_path.name
    # YYYY-MM-DD_HH-MM_hostname_title.html
    assert re.match(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_", name)
    assert "127-0-0-1" in name or "localhost" in name
    assert "_partial" not in name


@pytest.mark.asyncio
async def test_full_pipeline_ad_elements_removed(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    config = _test_config(include_dom_cleanup=True)
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/article"), config=config)

    await page_load_run(ctx)
    await image_dedup_run(ctx)
    await inline_run(ctx)

    output_path = _write_archive(ctx, tmp_path)
    content = output_path.read_text()
    assert "adsbygoogle" not in content
    assert "ad-banner" not in content
    assert "ad-unit" not in content
    assert 'width="1"' not in content  # tracking pixel


@pytest.mark.asyncio
async def test_full_pipeline_article_content_preserved(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    config = _test_config()
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/article"), config=config)

    await page_load_run(ctx)
    await image_dedup_run(ctx)
    await inline_run(ctx)

    output_path = _write_archive(ctx, tmp_path)
    content = output_path.read_text()
    assert "Remarkable New Species" in content
    assert "Dr. Elena Vasquez" in content
    assert "Nature Weekly" in content


# --- Partial save ---


@pytest.mark.asyncio
async def test_full_pipeline_partial_save_when_monolith_missing(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")

    # Point to a non-existent binary → triggers partial save
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: tmp_path / "nonexistent")

    config = _test_config()
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/article"), config=config)

    await page_load_run(ctx)
    await image_dedup_run(ctx)

    # Asset inlining should fail gracefully
    with pytest.raises(AssetInliningError):
        await inline_run(ctx)
    ctx.is_partial = True

    output_path = _write_archive(ctx, tmp_path)
    assert "_partial" in output_path.name


@pytest.mark.asyncio
async def test_full_pipeline_partial_file_has_content(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: tmp_path / "nonexistent")

    config = _test_config()
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/article"), config=config)

    await page_load_run(ctx)
    await image_dedup_run(ctx)

    with pytest.raises(AssetInliningError):
        await inline_run(ctx)
    ctx.is_partial = True

    output_path = _write_archive(ctx, tmp_path)
    content = output_path.read_text()
    assert "Remarkable New Species" in content


# --- Error cases ---


@pytest.mark.asyncio
async def test_full_pipeline_404_produces_error_page(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/missing").respond_with_data("Not Found", status=404)

    config = _test_config(timeout=5)
    config.output_dir = tmp_path
    ctx = ArchiveContext(url=httpserver.url_for("/missing"), config=config)

    with pytest.raises(PageLoadError):
        await page_load_run(ctx)

    # The CLI catches PageLoadError and produces an error page.
    # Replicate that logic here.
    import html as html_module
    from datetime import datetime

    escaped_error = html_module.escape(f"HTTP 404 for {httpserver.url_for('/missing')}"[:500])
    ctx.page_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Archive Error: {httpserver.url_for("/missing")}</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>Archive Error</h1>
    <p>Failed to archive: <a href="{httpserver.url_for("/missing")}">{httpserver.url_for("/missing")}</a></p>
    <p>Error: {escaped_error}</p>
    <p>Timestamp: {datetime.now().isoformat()}</p>
</body>
</html>"""
    ctx.page_title = f"Archive Error: {httpserver.url_for('/missing')}"
    ctx.final_url = httpserver.url_for("/missing")
    ctx.is_partial = True

    _write_archive(ctx, tmp_path)
    html_files = list(tmp_path.glob("*.html"))
    assert html_files, "Expected error page output file"


# --- CLI input validation (no Playwright needed) ---


def test_full_pipeline_invalid_url_exits_nonzero(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from archiveinator.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["archive", "not-a-url", "--output-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "Invalid URL" in result.output


# --- Optional: real monolith test (skipped if not installed) ---


@pytest.mark.e2e
def test_full_pipeline_real_monolith(httpserver: HTTPServer, tmp_path: Path) -> None:
    """Run the full pipeline with the real monolith binary if available."""
    from archiveinator.config import monolith_bin

    if not monolith_bin().exists():
        pytest.skip("monolith binary not installed — run 'archiveinator setup' first")

    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")

    from typer.testing import CliRunner

    from archiveinator.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1
    assert "_partial" not in html_files[0].name
    content = html_files[0].read_text()
    assert "Remarkable New Species" in content
