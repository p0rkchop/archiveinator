from __future__ import annotations

import pytest

from archiveinator.config import Config, UserAgent, UserAgentConfig
from archiveinator.pipeline import ArchiveContext


def _make_ctx(agents: list[UserAgent] | None = None) -> ArchiveContext:
    cfg = Config()
    if agents is not None:
        cfg.user_agents = UserAgentConfig(cycle=False, agents=agents)
    return ArchiveContext(url="https://example.com/article", config=cfg)


@pytest.mark.asyncio
async def test_run_sets_google_news_referer() -> None:
    from archiveinator.steps.google_news import run

    ctx = _make_ctx()
    await run(ctx)

    assert ctx.extra_headers.get("Referer") == "https://news.google.com/"


@pytest.mark.asyncio
async def test_run_sets_x_forwarded_for() -> None:
    from archiveinator.steps.google_news import run

    ctx = _make_ctx()
    await run(ctx)

    assert "X-Forwarded-For" in ctx.extra_headers


@pytest.mark.asyncio
async def test_run_uses_googlebot_ua_when_configured() -> None:
    from archiveinator.steps.google_news import run

    googlebot = UserAgent(name="googlebot", ua="Googlebot/2.1", enabled=True)
    ctx = _make_ctx(agents=[googlebot])
    await run(ctx)

    assert ctx.ua_override == "Googlebot/2.1"


@pytest.mark.asyncio
async def test_run_leaves_ua_override_none_without_googlebot() -> None:
    from archiveinator.steps.google_news import run

    chrome = UserAgent(name="chrome", ua="Mozilla/5.0 Chrome", enabled=True)
    ctx = _make_ctx(agents=[chrome])
    await run(ctx)

    assert ctx.ua_override is None
