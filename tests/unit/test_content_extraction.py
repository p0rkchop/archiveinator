from __future__ import annotations

import pytest
from pytest import MonkeyPatch

from archiveinator.config import Config
from archiveinator.pipeline import ArchiveContext


def _make_ctx(html: str = "", title: str = "Test") -> ArchiveContext:
    ctx = ArchiveContext(url="https://example.com/article", config=Config())
    ctx.page_html = html
    ctx.page_title = title
    ctx.final_url = "https://example.com/article"
    ctx.paywalled = True
    return ctx


@pytest.mark.asyncio
async def test_run_extracts_content_and_clears_paywalled(monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.content_extraction as mod

    monkeypatch.setattr(
        mod,
        "_FALLBACK_TEMPLATE",
        "{title}|{body}|{url}",
    )

    import types

    fake_trafilatura = types.ModuleType("trafilatura")
    fake_trafilatura.extract = lambda html, **kw: "<p>Article body</p>"  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", fake_trafilatura)

    from archiveinator.steps.content_extraction import run

    ctx = _make_ctx(html="<html><body><p>Article body</p></body></html>", title="My Article")
    await run(ctx)

    assert not ctx.paywalled
    assert ctx.bypass_method == "content_extraction"
    assert "Article body" in (ctx.page_html or "")


@pytest.mark.asyncio
async def test_run_raises_when_trafilatura_returns_none(monkeypatch: MonkeyPatch) -> None:
    import types

    fake_trafilatura = types.ModuleType("trafilatura")
    fake_trafilatura.extract = lambda html, **kw: None  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", fake_trafilatura)

    from archiveinator.steps.content_extraction import ContentExtractionError, run

    ctx = _make_ctx(html="<html><body></body></html>")
    with pytest.raises(ContentExtractionError):
        await run(ctx)


@pytest.mark.asyncio
async def test_run_raises_when_no_html() -> None:
    from archiveinator.steps.content_extraction import ContentExtractionError, run

    ctx = _make_ctx(html="")
    with pytest.raises(ContentExtractionError):
        await run(ctx)
