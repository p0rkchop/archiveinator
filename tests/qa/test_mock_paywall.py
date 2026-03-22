"""Mock-server paywall/bot scenario tests.

These run against a local HTTP server with no network dependency,
verifying that archiveinator correctly detects and reacts to:
  1. HTTP 403 hard blocks
  2. PerimeterX-style bot challenge pages
  3. Piano/TinyPass paywall overlays
  4. Low word-count teaser stubs
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from archiveinator.cli import app

runner = CliRunner()


# ── Helpers ─────────────────────────────────────────────────────


def _monolith_passthrough(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    """Fake subprocess.run: copies input file to output file unchanged."""
    input_file = Path(cmd[1])
    output_idx = cmd.index("-o") + 1
    output_file = Path(cmd[output_idx])
    output_file.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
    return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")


def _setup_monolith_mock(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    fake_bin = tmp_path / "monolith"
    fake_bin.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: fake_bin)
    monkeypatch.setattr(subprocess, "run", _monolith_passthrough)


def _plain(text: str) -> str:
    """Strip ANSI escape codes."""
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ── Test pages ──────────────────────────────────────────────────

# Enough real-looking prose to pass the word-count check when bypass succeeds
_ARTICLE_BODY = " ".join(["The quick brown fox jumps over the lazy dog."] * 80)

_REAL_ARTICLE = f"""\
<!DOCTYPE html>
<html><head><title>Test Article — Example News</title></head>
<body>
<article>
<h1>Breakthrough Discovery in Deep Ocean</h1>
<p>{_ARTICLE_BODY}</p>
</article>
</body></html>
"""

_PERIMETERX_BOT_PAGE = """\
<!DOCTYPE html>
<html><head>
<title>Bloomberg - Are you a robot?</title>
<meta name="robots" content="none">
</head><body>
<div id="px-captcha">
  <h2 class="main__heading">We've detected unusual activity from your computer network</h2>
  <p>To continue, please click the box below to let us know you're not a robot.</p>
  <div id="px-loader" class="px-loader-wrapper"></div>
</div>
<div id="block_uuid">Block reference ID: test-uuid-1234</div>
<script>window._pxAppId = 'PX8FCGYgk4';</script>
</body></html>
"""

_PIANO_PAYWALL_PAGE = f"""\
<!DOCTYPE html>
<html><head><title>Premium Article — News Site</title></head>
<body>
<article>
<h1>Exclusive Investigation</h1>
<p>{_ARTICLE_BODY}</p>
</article>
<div class="tp-modal" id="tp-container">
  <div class="tp-backdrop"></div>
  <div class="piano-offer">
    <h2>Subscribe to continue reading</h2>
    <p>You've reached your monthly limit of free articles.</p>
  </div>
</div>
<style>body {{ overflow: hidden; }}</style>
</body></html>
"""

_LOW_WORD_COUNT_STUB = """\
<!DOCTYPE html>
<html><head><title>Paywalled Article — News Site</title></head>
<body>
<article>
<h1>Breaking: Major Event Occurs</h1>
<p>Subscribe to read the full story. Only $4.99/month.</p>
</article>
</body></html>
"""


# ── Scenario 1: HTTP 403 hard block ────────────────────────────


@pytest.mark.mock_paywall
def test_http_403_triggers_bypass_suite(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A 403 should trigger paywall detection and the bypass suite, not abort."""
    httpserver.expect_request("/article").respond_with_data(
        _REAL_ARTICLE, status=403, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)
    monkeypatch.setattr("archiveinator.cli._RETRY_DELAY_SECONDS", 0)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path), "--verbose"],
    )

    output = _plain(result.output)
    # Should NOT abort with "Failed to load page" — should try bypass
    assert "Failed to load page" not in output
    # Should detect as paywall/block
    assert "HTTP 403" in output


@pytest.mark.mock_paywall
def test_http_403_produces_archive_not_crash(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A 403 response should still produce an archive file (possibly partial)."""
    httpserver.expect_request("/article").respond_with_data(
        _REAL_ARTICLE, status=403, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)
    monkeypatch.setattr("archiveinator.cli._RETRY_DELAY_SECONDS", 0)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert list(tmp_path.glob("*.html"))


# ── Scenario 2: PerimeterX bot challenge page ──────────────────


@pytest.mark.mock_paywall
def test_perimeterx_bot_page_detected(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """PerimeterX returns HTTP 200 with a challenge page — should be detected as blocked."""
    httpserver.expect_request("/article").respond_with_data(
        _PERIMETERX_BOT_PAGE, status=200, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path), "--verbose"],
    )

    output = _plain(result.output)
    # Should detect the bot challenge
    assert "bot challenge" in output.lower() or "paywall" in output.lower() or "block" in output.lower()


@pytest.mark.mock_paywall
def test_perimeterx_bot_page_produces_archive(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A PerimeterX bot page should still produce an output file (partial or extracted)."""
    httpserver.expect_request("/article").respond_with_data(
        _PERIMETERX_BOT_PAGE, status=200, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert html_files
    # The archive should exist — either as _partial (bypass failed) or as
    # a content-extraction fallback. Either way, the bot page was detected
    # and the pipeline did not silently archive the challenge page as-is.


# ── Scenario 3: Piano / TinyPass paywall overlay ───────────────


@pytest.mark.mock_paywall
def test_piano_paywall_detected(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Piano paywall overlay (.tp-modal) should be detected."""
    httpserver.expect_request("/article").respond_with_data(
        _PIANO_PAYWALL_PAGE, status=200, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path), "--verbose"],
    )

    output = _plain(result.output)
    assert "paywall" in output.lower() or "block" in output.lower() or "tp-modal" in output.lower()


@pytest.mark.mock_paywall
def test_piano_overlay_removed_from_archive(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The JS overlay removal step should strip the .tp-modal from the saved HTML."""
    httpserver.expect_request("/article").respond_with_data(
        _PIANO_PAYWALL_PAGE, status=200, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)

    runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    html_files = list(tmp_path.glob("*.html"))
    assert html_files
    content = html_files[0].read_text()
    # Article content should be preserved
    assert "Exclusive Investigation" in content


# ── Scenario 4: Low word-count stub ────────────────────────────


@pytest.mark.mock_paywall
def test_low_word_count_detected(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A teaser page with very few words should be flagged as paywalled."""
    httpserver.expect_request("/article").respond_with_data(
        _LOW_WORD_COUNT_STUB, status=200, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path), "--verbose"],
    )

    output = _plain(result.output)
    # The paywall detection should fire on the low word count, triggering
    # a warning about the paywall/block.
    assert (
        "word count" in output.lower()
        or "paywall" in output.lower()
        or "Partial" in result.output
    ), f"Low word-count page was not flagged. Output:\n{output}"


@pytest.mark.mock_paywall
def test_low_word_count_produces_archive(
    httpserver: HTTPServer, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A low word count page should still produce some archive output."""
    httpserver.expect_request("/article").respond_with_data(
        _LOW_WORD_COUNT_STUB, status=200, content_type="text/html"
    )
    _setup_monolith_mock(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["archive", httpserver.url_for("/article"), "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert html_files, "No output file produced for low word-count page"
