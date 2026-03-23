from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_apply_calls_stealth_async() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps import stealth_browser

    page = MagicMock()
    stealth_browser._stealth.apply_stealth_async = AsyncMock()

    await stealth_browser.apply(page)

    stealth_browser._stealth.apply_stealth_async.assert_called_once_with(page)


def test_module_step_name() -> None:
    from archiveinator.steps.stealth_browser import STEP

    assert STEP == "stealth_browser"
