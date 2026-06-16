from __future__ import annotations

import pytest

from archiveinator.config import Config
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.js_strip import run


def _ctx(html: str) -> ArchiveContext:
    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = html
    return ctx


@pytest.mark.asyncio
async def test_script_tags_removed() -> None:
    ctx = _ctx(
        "<html><head><script>alert('xss')</script></head>"
        "<body><script src='app.js'></script><p>Hello</p></body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "<script" not in ctx.page_html
    assert "Hello" in ctx.page_html


@pytest.mark.asyncio
async def test_noscript_tags_removed() -> None:
    ctx = _ctx("<html><body><noscript>Please enable JS</noscript><p>Content</p></body></html>")
    await run(ctx)
    assert ctx.page_html is not None
    assert "<noscript" not in ctx.page_html
    assert "Content" in ctx.page_html


@pytest.mark.asyncio
async def test_inline_event_handlers_removed() -> None:
    ctx = _ctx(
        "<html><body>"
        '<button onclick="doSomething()">Click</button>'
        '<a href="/page" onmouseover="track()">Link</a>'
        '<div onload="init()">Div</div>'
        "</body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "onclick" not in ctx.page_html
    assert "onmouseover" not in ctx.page_html
    assert "onload" not in ctx.page_html
    # Non-JS attributes preserved
    assert 'href="/page"' in ctx.page_html


@pytest.mark.asyncio
async def test_javascript_href_removed() -> None:
    ctx = _ctx(
        "<html><body>"
        '<a href="javascript:void(0)">Click me</a>'
        '<a href="/real-link">Real link</a>'
        "</body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "javascript:" not in ctx.page_html
    # Real href preserved
    assert 'href="/real-link"' in ctx.page_html


@pytest.mark.asyncio
async def test_noop_when_no_html() -> None:
    ctx = _ctx("")
    ctx.page_html = None
    await run(ctx)
    assert ctx.page_html is None


@pytest.mark.asyncio
async def test_regular_content_preserved() -> None:
    ctx = _ctx(
        "<html><head><title>Test</title></head>"
        "<body><h1>Article</h1><p>Body text</p>"
        '<img src="photo.jpg" alt="Photo">'
        "</body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "<h1>Article</h1>" in ctx.page_html
    assert "Body text" in ctx.page_html
    assert 'src="photo.jpg"' in ctx.page_html
