"""Unit tests for the curl_impersonate step."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from archiveinator.steps.curl_impersonate import _BINARY_NAMES, STEP, find_binary


def test_step_name() -> None:
    assert STEP == "curl_impersonate"


def test_binary_names_ordering() -> None:
    """Newest Chrome impersonation binary should be first in probe list."""
    assert _BINARY_NAMES[0] == "curl_chrome124"
    assert len(_BINARY_NAMES) >= 3


def test_find_binary_returns_none_when_absent() -> None:
    """Returns None when no curl-impersonate binary is in PATH."""
    with patch("shutil.which", return_value=None):
        result = find_binary()
    assert result is None


def test_find_binary_returns_first_found() -> None:
    """Returns the first binary found in PATH, not subsequent ones."""

    def which_side_effect(name: str) -> str | None:
        if name == "curl_chrome124":
            return "/usr/local/bin/curl_chrome124"
        return None

    with patch("shutil.which", side_effect=which_side_effect):
        result = find_binary()

    assert result == Path("/usr/local/bin/curl_chrome124")


@pytest.mark.asyncio
async def test_skips_when_no_binary() -> None:
    """Step exits silently without modifying ctx when binary is not found."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.curl_impersonate import run

    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = "<html>original</html>"

    with patch("archiveinator.steps.curl_impersonate.find_binary", return_value=None):
        await run(ctx)

    assert ctx.page_html == "<html>original</html>"


@pytest.mark.asyncio
async def test_skips_on_non_200_status() -> None:
    """Step exits silently when curl-impersonate returns a non-200 status."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.curl_impersonate import run

    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = "<html>original</html>"

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"403", b""))

    with (
        patch(
            "archiveinator.steps.curl_impersonate.find_binary",
            return_value=Path("/usr/local/bin/curl_chrome124"),
        ),
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)),
    ):
        await run(ctx)

    assert ctx.page_html == "<html>original</html>"


@pytest.mark.asyncio
async def test_sets_page_html_on_success(tmp_path: Path) -> None:
    """Sets ctx.page_html when curl-impersonate returns HTTP 200 with content."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.curl_impersonate import run

    ctx = ArchiveContext(url="https://example.com", config=Config())

    html_content = "<html><body>" + " ".join(["word"] * 200) + "</body></html>"

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"200", b""))

    def fake_named_temp(*args: object, **kwargs: object) -> MagicMock:
        mock_file = MagicMock()
        html_file = tmp_path / "test_output.html"
        html_file.write_text(html_content)
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.name = str(html_file)
        return mock_file

    with (
        patch(
            "archiveinator.steps.curl_impersonate.find_binary",
            return_value=Path("/usr/local/bin/curl_chrome124"),
        ),
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)),
        patch("tempfile.NamedTemporaryFile", side_effect=fake_named_temp),
        patch("archiveinator.steps.curl_impersonate._detect_paywall_from_html"),
    ):
        await run(ctx)

    assert ctx.page_html == html_content


def test_detect_paywall_from_html_clears_on_clean_content() -> None:
    """Clean long-form HTML should result in paywalled=False."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.curl_impersonate import _detect_paywall_from_html

    ctx = ArchiveContext(url="https://example.com", config=Config())
    html = "<html><body>" + " ".join(["article"] * 300) + "</body></html>"

    _detect_paywall_from_html(ctx, html)

    assert ctx.paywalled is False


def test_detect_paywall_from_html_flags_low_word_count() -> None:
    """Minimal HTML should be flagged as paywalled due to low word count."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.curl_impersonate import _detect_paywall_from_html

    ctx = ArchiveContext(url="https://example.com", config=Config())
    html = "<html><body><p>Too short</p></body></html>"

    _detect_paywall_from_html(ctx, html)

    assert ctx.paywalled is True
    assert "word count" in (ctx.paywall_reason or "").lower()
