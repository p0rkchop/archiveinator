from __future__ import annotations

import pytest
from pytest import MonkeyPatch
from pytest_httpserver import HTTPServer

from archiveinator.blocklist import _build_engine
from archiveinator.config import Config, PipelineStep
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.page_load import run

_PAGE_TEMPLATE = """\
<html>
<head><title>Ad Blocking Test</title></head>
<body>
<p>Content</p>
<script src="{ad_url}"></script>
<script src="{safe_url}"></script>
</body>
</html>
"""

_AD_SCRIPT = "console.log('ad loaded');"
_SAFE_SCRIPT = "console.log('safe loaded');"


def _config_with_ad_blocking(timeout: int = 15) -> Config:
    config = Config()
    config.timeout_seconds = timeout
    config.pipeline = [
        PipelineStep(step="network_ad_blocking", enabled=True),
        PipelineStep(step="page_load", enabled=True),
        PipelineStep(step="asset_inlining", enabled=True),
    ]
    return config


def _config_without_ad_blocking(timeout: int = 15) -> Config:
    config = Config()
    config.timeout_seconds = timeout
    config.pipeline = [
        PipelineStep(step="page_load", enabled=True),
        PipelineStep(step="asset_inlining", enabled=True),
    ]
    return config


@pytest.mark.asyncio
async def test_ad_request_is_blocked(httpserver: HTTPServer, monkeypatch: MonkeyPatch) -> None:
    """Requests matching ad rules should be aborted before reaching the server."""
    import archiveinator.blocklist as bl_mod

    ad_path = "/ads/banner.js"
    safe_path = "/static/app.js"

    ad_requested: list[bool] = []
    safe_requested: list[bool] = []

    def ad_handler(request: object) -> None:
        from werkzeug.wrappers import Response

        ad_requested.append(True)
        return Response(_AD_SCRIPT, content_type="application/javascript")

    def safe_handler(request: object) -> None:
        from werkzeug.wrappers import Response

        safe_requested.append(True)
        return Response(_SAFE_SCRIPT, content_type="application/javascript")

    httpserver.expect_request(ad_path).respond_with_handler(ad_handler)
    httpserver.expect_request(safe_path).respond_with_handler(safe_handler)

    ad_url = httpserver.url_for(ad_path)
    safe_url = httpserver.url_for(safe_path)
    page_html = _PAGE_TEMPLATE.format(ad_url=ad_url, safe_url=safe_url)
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    # Path-based rule — works reliably with localhost test servers
    monkeypatch.setattr(bl_mod, "load_engine", lambda: _build_engine(["/ads/banner.js"]))

    config = _config_with_ad_blocking()
    ctx = ArchiveContext(url=httpserver.url_for("/"), config=config)
    await run(ctx)

    assert ctx.page_html is not None
    assert safe_requested, "Safe script was unexpectedly blocked"
    assert not ad_requested, "Ad script was not blocked"


@pytest.mark.asyncio
async def test_ad_blocking_disabled_allows_all_requests(
    httpserver: HTTPServer, monkeypatch: MonkeyPatch
) -> None:
    """When network_ad_blocking is not in the pipeline, all requests go through."""
    import archiveinator.blocklist as bl_mod

    ad_path = "/ads/banner.js"
    safe_path = "/static/app.js"
    ad_requested: list[bool] = []

    def ad_handler(request: object) -> None:
        from werkzeug.wrappers import Response

        ad_requested.append(True)
        return Response(_AD_SCRIPT, content_type="application/javascript")

    httpserver.expect_request(ad_path).respond_with_handler(ad_handler)
    httpserver.expect_request(safe_path).respond_with_data(
        _SAFE_SCRIPT, content_type="application/javascript"
    )

    page_html = _PAGE_TEMPLATE.format(
        ad_url=httpserver.url_for(ad_path),
        safe_url=httpserver.url_for(safe_path),
    )
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")

    monkeypatch.setattr(bl_mod, "load_engine", lambda: _build_engine(["/ads/banner.js"]))

    config = _config_without_ad_blocking()
    ctx = ArchiveContext(url=httpserver.url_for("/"), config=config)
    await run(ctx)

    assert ctx.page_html is not None
    assert ad_requested, "Ad script should have loaded when blocking is disabled"


@pytest.mark.asyncio
async def test_page_still_loads_when_ad_blocked(
    httpserver: HTTPServer, monkeypatch: MonkeyPatch
) -> None:
    """Blocking ad requests must not prevent the main page from loading."""
    import archiveinator.blocklist as bl_mod

    ad_path = "/ads/tracker.js"
    page_html = (
        f"<html><head><title>Clean Page</title></head>"
        f"<body><p>Article content</p>"
        f'<script src="{httpserver.url_for(ad_path)}"></script>'
        f"</body></html>"
    )
    httpserver.expect_request("/").respond_with_data(page_html, content_type="text/html")
    httpserver.expect_request(ad_path).respond_with_data(
        _AD_SCRIPT, content_type="application/javascript"
    )

    monkeypatch.setattr(bl_mod, "load_engine", lambda: _build_engine(["/ads/"]))

    config = _config_with_ad_blocking()
    ctx = ArchiveContext(url=httpserver.url_for("/"), config=config)
    await run(ctx)

    assert ctx.page_html is not None
    assert ctx.page_title == "Clean Page"
    assert "Article content" in ctx.page_html
