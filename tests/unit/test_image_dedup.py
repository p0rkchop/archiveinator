from __future__ import annotations

import pytest

from archiveinator.config import Config
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.image_dedup import run


def _ctx(html: str) -> ArchiveContext:
    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = html
    return ctx


# --- srcset resolution ---


@pytest.mark.asyncio
async def test_srcset_replaced_with_best_width() -> None:
    ctx = _ctx(
        "<html><body>"
        '<img src="img.jpg?w=320" srcset="img.jpg?w=320 320w, img.jpg?w=768 768w, img.jpg?w=1200 1200w">'
        "</body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "srcset" not in ctx.page_html
    assert "img.jpg?w=1200" in ctx.page_html


@pytest.mark.asyncio
async def test_srcset_picks_largest_under_max_width() -> None:
    ctx = _ctx(
        "<html><body>"
        '<img srcset="img.jpg?w=400 400w, img.jpg?w=800 800w, img.jpg?w=2000 2000w">'
        "</body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "img.jpg?w=800" in ctx.page_html
    assert "srcset" not in ctx.page_html


@pytest.mark.asyncio
async def test_srcset_picks_smallest_when_all_exceed_max() -> None:
    ctx = _ctx(
        '<html><body><img srcset="img.jpg?w=1400 1400w, img.jpg?w=2000 2000w"></body></html>'
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "img.jpg?w=1400" in ctx.page_html


@pytest.mark.asyncio
async def test_img_without_srcset_unchanged() -> None:
    html = '<html><body><img src="photo.jpg"></body></html>'
    ctx = _ctx(html)
    await run(ctx)
    assert ctx.page_html is not None
    assert "photo.jpg" in ctx.page_html


# --- picture collapse ---


@pytest.mark.asyncio
async def test_picture_collapsed_to_img() -> None:
    ctx = _ctx(
        "<html><body>"
        "<picture>"
        '<source srcset="hero-small.webp 600w, hero-large.webp 1200w">'
        '<img src="hero-fallback.jpg">'
        "</picture>"
        "</body></html>"
    )
    await run(ctx)
    assert ctx.page_html is not None
    assert "<picture>" not in ctx.page_html
    assert "<img" in ctx.page_html
    assert "hero-large.webp" in ctx.page_html


@pytest.mark.asyncio
async def test_picture_with_no_source_keeps_img_src() -> None:
    ctx = _ctx('<html><body><picture><img src="fallback.jpg"></picture></body></html>')
    await run(ctx)
    assert ctx.page_html is not None
    assert "<picture>" not in ctx.page_html
    assert "fallback.jpg" in ctx.page_html


# --- no-op cases ---


@pytest.mark.asyncio
async def test_no_op_when_page_html_is_none() -> None:
    ctx = ArchiveContext(url="https://example.com", config=Config())
    ctx.page_html = None
    await run(ctx)  # should not raise
    assert ctx.page_html is None


@pytest.mark.asyncio
async def test_no_op_when_no_responsive_images() -> None:
    html = '<html><body><img src="photo.jpg"><p>text</p></body></html>'
    ctx = _ctx(html)
    await run(ctx)
    assert ctx.page_html is not None
    assert "photo.jpg" in ctx.page_html
