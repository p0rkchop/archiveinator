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
    fake_trafilatura.extract = lambda html, **kw: "<p>" + " ".join(["word"] * 60) + "</p>"  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", fake_trafilatura)

    from archiveinator.steps.content_extraction import run

    ctx = _make_ctx(html="<html><body><p>Article body</p></body></html>", title="My Article")
    await run(ctx)

    assert not ctx.paywalled
    assert ctx.bypass_method == "content_extraction"
    assert "word" in (ctx.page_html or "")


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
async def test_run_raises_when_content_too_short(monkeypatch: MonkeyPatch) -> None:
    """Extraction that returns fewer than 50 plain-text words is rejected."""
    import types

    fake_trafilatura = types.ModuleType("trafilatura")
    # Simulate a Cloudflare challenge page extraction: very few words
    fake_trafilatura.extract = lambda html, **kw: "<p>Just a moment...</p>"  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "trafilatura", fake_trafilatura)

    from archiveinator.steps.content_extraction import ContentExtractionError, run

    ctx = _make_ctx(html="<html><body><p>Just a moment...</p></body></html>")
    with pytest.raises(ContentExtractionError, match="too short"):
        await run(ctx)


@pytest.mark.asyncio
async def test_run_raises_when_no_html() -> None:
    from archiveinator.steps.content_extraction import ContentExtractionError, run

    ctx = _make_ctx(html="")
    with pytest.raises(ContentExtractionError):
        await run(ctx)
