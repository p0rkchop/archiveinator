from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_check_wayback_returns_url_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.archive_fallback import check_wayback

    snapshot_url = "https://web.archive.org/web/20240101/https://example.com"
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "archived_snapshots": {
            "closest": {
                "available": True,
                "url": snapshot_url,
            },
        },
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    result = await check_wayback("https://example.com")
    assert result == snapshot_url


@pytest.mark.asyncio
async def test_check_wayback_returns_none_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, MagicMock

    from archiveinator.steps.archive_fallback import check_wayback

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "archived_snapshots": {},
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    result = await check_wayback("https://example.com")
    assert result is None


@pytest.mark.asyncio
async def test_check_wayback_returns_none_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from archiveinator.steps.archive_fallback import check_wayback

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPError("Service unavailable")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    result = await check_wayback("https://example.com")
    assert result is None


def test_module_step_name() -> None:
    from archiveinator.steps.archive_fallback import STEP

    assert STEP == "archive_fallback"
