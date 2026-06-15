"""Unit tests for the flaresolverr step."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from archiveinator.steps.flaresolverr import STEP, _get_flaresolverr_url


def test_step_name() -> None:
    assert STEP == "flaresolverr"


def test_get_url_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns None when neither config nor env var is set."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext

    monkeypatch.delenv("FLARESOLVERR_URL", raising=False)
    ctx = ArchiveContext(url="https://example.com", config=Config())
    assert _get_flaresolverr_url(ctx) is None


def test_get_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reads URL from FLARESOLVERR_URL env var."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext

    monkeypatch.setenv("FLARESOLVERR_URL", "http://flaresolverr:8191/v1")
    ctx = ArchiveContext(url="https://example.com", config=Config())
    assert _get_flaresolverr_url(ctx) == "http://flaresolverr:8191/v1"


def test_get_url_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reads URL from config.flaresolverr_url."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext

    monkeypatch.delenv("FLARESOLVERR_URL", raising=False)
    config = Config()
    config.flaresolverr_url = "http://localhost:8191/v1"
    ctx = ArchiveContext(url="https://example.com", config=config)
    assert _get_flaresolverr_url(ctx) == "http://localhost:8191/v1"


@pytest.mark.asyncio
async def test_skips_when_no_url_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Step exits silently when no FlareSolverr URL is configured."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.flaresolverr import run

    monkeypatch.delenv("FLARESOLVERR_URL", raising=False)
    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.cookies = []

    await run(ctx)  # Should not raise

    assert ctx.cookies == []


@pytest.mark.asyncio
async def test_skips_when_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Step exits silently when FlareSolverr is not reachable."""
    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.flaresolverr import run

    monkeypatch.setenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.cookies = []

    with patch("archiveinator.steps.flaresolverr._is_available", AsyncMock(return_value=False)):
        await run(ctx)

    assert ctx.cookies == []


@pytest.mark.asyncio
async def test_injects_cookies_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cookies and user agent are injected when FlareSolverr returns a solution."""
    import httpx

    from archiveinator.config import Config
    from archiveinator.pipeline import ArchiveContext
    from archiveinator.steps.flaresolverr import run

    monkeypatch.setenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.cookies = []

    fake_cookies = [{"name": "cf_clearance", "value": "abc123", "domain": "example.com"}]
    fake_response_body = {
        "status": "ok",
        "solution": {
            "cookies": fake_cookies,
            "userAgent": "Mozilla/5.0 (FlareSolverr Chrome)",
        },
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json = lambda: fake_response_body
    mock_resp.raise_for_status = lambda: None

    with (
        patch("archiveinator.steps.flaresolverr._is_available", AsyncMock(return_value=True)),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        await run(ctx)

    assert any(c["name"] == "cf_clearance" for c in (ctx.cookies or []))
    assert ctx.ua_override == "Mozilla/5.0 (FlareSolverr Chrome)"
