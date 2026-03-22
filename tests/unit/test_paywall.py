from __future__ import annotations

import pytest

# --- detect() ---


@pytest.mark.asyncio
async def test_detect_returns_none_for_clean_page() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.paywall import detect

    page = MagicMock()
    # Order: bot_selector, bot_title, paywall_selector, word_count
    page.evaluate = AsyncMock(side_effect=[None, None, None, 800])

    result = await detect(page, http_status=200)
    assert result is None


@pytest.mark.asyncio
async def test_detect_triggers_on_paywall_http_status() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.paywall import detect

    page = MagicMock()
    page.evaluate = AsyncMock(return_value=None)

    result = await detect(page, http_status=403)
    assert result is not None
    assert "403" in result


@pytest.mark.asyncio
async def test_detect_triggers_on_402() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.paywall import detect

    page = MagicMock()
    page.evaluate = AsyncMock(return_value=None)

    result = await detect(page, http_status=402)
    assert result is not None


@pytest.mark.asyncio
async def test_detect_triggers_on_dom_selector() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.paywall import detect

    page = MagicMock()
    # Order: bot_selector → None, bot_title → None, paywall_selector → match
    page.evaluate = AsyncMock(side_effect=[None, None, ".tp-modal"])

    result = await detect(page, http_status=200)
    assert result is not None
    assert ".tp-modal" in result


@pytest.mark.asyncio
async def test_detect_triggers_on_low_word_count() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.paywall import detect

    page = MagicMock()
    # Order: bot_selector, bot_title, paywall_selector, word_count
    page.evaluate = AsyncMock(side_effect=[None, None, None, 42])

    result = await detect(page, http_status=200)
    assert result is not None
    assert "42" in result


@pytest.mark.asyncio
async def test_detect_ignores_zero_word_count() -> None:
    """A word count of 0 could be a JS-heavy SPA loading; don't flag it."""
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.paywall import detect

    page = MagicMock()
    # Order: bot_selector, bot_title, paywall_selector, word_count
    page.evaluate = AsyncMock(side_effect=[None, None, None, 0])

    result = await detect(page, http_status=200)
    assert result is None
