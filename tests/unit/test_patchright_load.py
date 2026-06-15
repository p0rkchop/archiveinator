"""Unit tests for the patchright_load step."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from archiveinator.steps.patchright_load import STEP, PatchrightLoadError


def test_step_name() -> None:
    assert STEP == "patchright_load"


def test_error_class() -> None:
    err = PatchrightLoadError("test")
    assert isinstance(err, Exception)
    assert str(err) == "test"


@pytest.mark.asyncio
async def test_skips_gracefully_when_not_installed() -> None:
    """Step should exit silently and leave ctx unchanged when patchright is absent."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.patchright_load import run

    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = "<html>original</html>"

    with patch.dict(sys.modules, {"patchright": None, "patchright.async_api": None}):
        await run(ctx)

    # ctx should be unchanged
    assert ctx.page_html == "<html>original</html>"


@pytest.mark.asyncio
async def test_raises_patchright_load_error_on_no_response() -> None:
    """Raises PatchrightLoadError if page.goto() returns None."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.patchright_load import run

    ctx = ArchiveContext(url="https://example.com", config=Config())

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.url = "https://example.com"
    mock_page.title = AsyncMock(return_value="")
    mock_page.content = AsyncMock(return_value="")
    mock_page.wait_for_load_state = AsyncMock(side_effect=Exception("timeout"))

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.add_cookies = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)
    mock_browser.close = AsyncMock()

    mock_p = AsyncMock()
    mock_p.chromium = MagicMock()
    mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_p.__aenter__ = AsyncMock(return_value=mock_p)
    mock_p.__aexit__ = AsyncMock(return_value=None)

    mock_patchright_module = MagicMock()
    mock_patchright_module.async_playwright = MagicMock(return_value=mock_p)

    with (
        patch.dict(
            sys.modules, {"patchright": MagicMock(), "patchright.async_api": mock_patchright_module}
        ),
        pytest.raises(PatchrightLoadError, match="No response"),
    ):
        await run(ctx)
