"""Unit tests for the camoufox_load step."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from archiveinator.steps.camoufox_load import STEP, CamoufoxLoadError


def test_step_name() -> None:
    assert STEP == "camoufox_load"


def test_error_class() -> None:
    err = CamoufoxLoadError("test error")
    assert isinstance(err, Exception)
    assert "test error" in str(err)


@pytest.mark.asyncio
async def test_skips_gracefully_when_not_installed() -> None:
    """Step exits silently and leaves ctx unchanged when camoufox is absent."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.camoufox_load import run

    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = "<html>original</html>"

    with patch.dict(sys.modules, {"camoufox": None, "camoufox.async_api": None}):
        await run(ctx)

    assert ctx.page_html == "<html>original</html>"


@pytest.mark.asyncio
async def test_raises_on_no_response() -> None:
    """Raises CamoufoxLoadError if page.goto() returns None."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.camoufox_load import run

    ctx = ArchiveContext(url="https://example.com", config=Config())

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.url = "https://example.com"
    mock_page.wait_for_load_state = AsyncMock(side_effect=Exception("timeout"))

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)

    mock_async_camoufox_cls = MagicMock(return_value=mock_browser)

    mock_camoufox_api = MagicMock()
    mock_camoufox_api.AsyncCamoufox = mock_async_camoufox_cls

    with (
        patch.dict(sys.modules, {"camoufox": MagicMock(), "camoufox.async_api": mock_camoufox_api}),
        pytest.raises(CamoufoxLoadError, match="No response"),
    ):
        await run(ctx)


@pytest.mark.asyncio
async def test_successful_load_updates_ctx() -> None:
    """On success, ctx.page_html, ctx.page_title, ctx.response_status are set."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.camoufox_load import run

    ctx = ArchiveContext(url="https://example.com", config=Config())

    mock_response = MagicMock()
    mock_response.status = 200

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(return_value=mock_response)
    mock_page.url = "https://example.com"
    mock_page.wait_for_load_state = AsyncMock(return_value=None)
    mock_page.content = AsyncMock(return_value="<html><body>Article content here</body></html>")
    mock_page.title = AsyncMock(return_value="Test Article")

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)

    mock_async_camoufox_cls = MagicMock(return_value=mock_browser)

    mock_camoufox_api = MagicMock()
    mock_camoufox_api.AsyncCamoufox = mock_async_camoufox_cls

    with (
        patch.dict(sys.modules, {"camoufox": MagicMock(), "camoufox.async_api": mock_camoufox_api}),
        patch("archiveinator.steps.paywall.detect", AsyncMock()),
    ):
        await run(ctx)

    assert ctx.page_html == "<html><body>Article content here</body></html>"
    assert ctx.page_title == "Test Article"
    assert ctx.response_status == 200
