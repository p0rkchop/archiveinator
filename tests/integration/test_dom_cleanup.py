from __future__ import annotations

import pytest
from pytest_httpserver import HTTPServer

from archiveinator.config import Config, PipelineStep
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.page_load import run


def _config(dom_cleanup: bool = True, timeout: int = 15) -> Config:
    config = Config()
    config.timeout_seconds = timeout
    steps = [PipelineStep(step="page_load", enabled=True)]
    if dom_cleanup:
        steps.insert(0, PipelineStep(step="dom_ad_cleanup", enabled=True))
    steps.append(PipelineStep(step="asset_inlining", enabled=True))
    config.pipeline = steps
    return config


def _page(body: str, title: str = "Test") -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


@pytest.mark.asyncio
async def test_google_ad_element_removed(httpserver: HTTPServer) -> None:
    page_html = _page('<ins class="adsbygoogle" data-ad-slot="123"></ins><p>Article</p>')
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert "adsbygoogle" not in ctx.page_html
    assert "Article" in ctx.page_html


@pytest.mark.asyncio
async def test_ad_container_by_class_removed(httpserver: HTTPServer) -> None:
    page_html = _page('<div class="ad-unit"><img src="ad.gif"/></div><p>Content</p>')
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert "ad-unit" not in ctx.page_html
    assert "Content" in ctx.page_html


@pytest.mark.asyncio
async def test_sponsored_content_removed(httpserver: HTTPServer) -> None:
    page_html = _page('<div class="sponsored-widget">Buy now!</div><p>Real content</p>')
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert "sponsored-widget" not in ctx.page_html
    assert "Real content" in ctx.page_html


@pytest.mark.asyncio
async def test_tracking_pixel_removed(httpserver: HTTPServer) -> None:
    page_html = _page('<img width="1" height="1" src="https://track.example.com/px"/><p>Story</p>')
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert 'width="1"' not in ctx.page_html
    assert "Story" in ctx.page_html


@pytest.mark.asyncio
async def test_non_ad_content_preserved(httpserver: HTTPServer) -> None:
    page_html = _page(
        "<h1>Title</h1><p>Paragraph one.</p><img src='photo.jpg'/><p>Paragraph two.</p>"
    )
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert "Paragraph one" in ctx.page_html
    assert "Paragraph two" in ctx.page_html
    assert "photo.jpg" in ctx.page_html


@pytest.mark.asyncio
async def test_multiple_ad_elements_all_removed(httpserver: HTTPServer) -> None:
    page_html = _page(
        '<ins class="adsbygoogle"></ins>'
        '<div class="ad-banner">ad</div>'
        '<div class="advertisement">ad2</div>'
        "<p>Keep this</p>"
    )
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert "adsbygoogle" not in ctx.page_html
    assert "ad-banner" not in ctx.page_html
    assert "advertisement" not in ctx.page_html
    assert "Keep this" in ctx.page_html


@pytest.mark.asyncio
async def test_dom_cleanup_disabled_leaves_ad_elements(httpserver: HTTPServer) -> None:
    page_html = _page('<ins class="adsbygoogle"></ins><p>Content</p>')
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config(dom_cleanup=False))
    await run(ctx)

    assert ctx.page_html is not None
    assert "adsbygoogle" in ctx.page_html
