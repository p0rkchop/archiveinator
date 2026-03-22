from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_remove_returns_count() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.js_overlay import remove

    page = MagicMock()
    page.evaluate = AsyncMock(return_value=3)

    count = await remove(page)
    assert count == 3


@pytest.mark.asyncio
async def test_remove_returns_zero_when_nothing_found() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.js_overlay import remove

    page = MagicMock()
    page.evaluate = AsyncMock(return_value=0)

    count = await remove(page)
    assert count == 0
