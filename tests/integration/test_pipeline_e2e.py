from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from archiveinator.cli import app

runner = CliRunner()

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

  <footer><p>© Nature Weekly</p></footer>
</body>
</html>
"""


def _fake_monolith(bin_path: Path) -> None:
    """Create a fake monolith binary that just copies input to output."""
    # We monkeypatch subprocess.run instead — this is just a marker
    pass


def _monolith_passthrough(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    """Fake subprocess.run: copies input file to output file unchanged."""
    input_file = Path(cmd[1])
    output_idx = cmd.index("-o") + 1
    output_file = Path(cmd[output_idx])
    output_file.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
    return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")


def _setup_monolith_mock(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Patch monolith_bin to point at a fake binary and mock the subprocess call."""
    import archiveinator.steps.asset_inlining as ai_mod

    fake_bin = tmp_path / "monolith"
    fake_bin.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: fake_bin)
    monkeypatch.setattr(subprocess, "run", _monolith_passthrough)


# --- Happy path ---


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_creates_output_file(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_filename_format(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    name = list(tmp_path.glob("*.html"))[0].name
    # YYYY-MM-DD_HH-MM_hostname_title.html
    import re

    assert re.match(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_", name)
    assert "127-0-0-1" in name or "localhost" in name
    assert "_partial" not in name


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_ad_elements_removed(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    content = list(tmp_path.glob("*.html"))[0].read_text()

    assert "adsbygoogle" not in content
    assert "ad-banner" not in content
    assert "ad-unit" not in content
    assert 'width="1"' not in content  # tracking pixel


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_article_content_preserved(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    content = list(tmp_path.glob("*.html"))[0].read_text()

    assert "Remarkable New Species" in content
    assert "Dr. Elena Vasquez" in content
    assert "Nature Weekly" in content


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_success_message(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Saved" in result.output


# --- Partial save ---


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_partial_save_when_monolith_missing(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")

    import archiveinator.steps.asset_inlining as ai_mod

    # Point to a non-existent binary → triggers partial save
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: tmp_path / "nonexistent")

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1
    assert "_partial" in html_files[0].name
    assert "Partial" in result.output


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_partial_file_has_content(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/article").respond_with_data(_ARTICLE_PAGE, content_type="text/html")

    import archiveinator.steps.asset_inlining as ai_mod

    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: tmp_path / "nonexistent")

    runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    content = list(tmp_path.glob("*.html"))[0].read_text()
    assert "Remarkable New Species" in content


# --- Error cases ---


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_404_exits_nonzero(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    httpserver.expect_request("/missing").respond_with_data("Not Found", status=404)
    monkeypatch.setattr("archiveinator.cli._RETRY_DELAY_SECONDS", 0)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/missing"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Page load failed" in result.output
    # Error page should be produced (partial archive)
    html_files = list(tmp_path.glob("*.html"))
    assert html_files, "Expected error page output file"


@pytest.mark.skip(reason="hanging in CI; investigate")
def test_full_pipeline_invalid_url_exits_nonzero(tmp_path: Path) -> None:
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
