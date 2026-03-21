from __future__ import annotations

import pytest
from pytest_httpserver import HTTPServer

from archiveinator.config import Config
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.page_load import PageLoadError, run

SIMPLE_PAGE = """\
<html>
<head><title>Test Article</title></head>
<body><p>Hello from the test server.</p></body>
</html>
"""

JS_RENDERED_PAGE = """\
<html>
<head><title>JS Page</title></head>
<body>
<p id="content"></p>
<script>
  document.getElementById("content").textContent = "Rendered by JS";
</script>
</body>
</html>
"""


def _config(timeout: int = 15) -> Config:
    config = Config()
    config.timeout_seconds = timeout
    return config


@pytest.mark.asyncio
async def test_page_load_basic(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/").respond_with_data(SIMPLE_PAGE, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_html is not None
    assert "Hello from the test server" in ctx.page_html
    assert ctx.page_title == "Test Article"
    assert ctx.final_url is not None


@pytest.mark.asyncio
async def test_page_load_captures_title(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/").respond_with_data(SIMPLE_PAGE, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert ctx.page_title == "Test Article"


@pytest.mark.asyncio
async def test_page_load_js_rendered_content(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/").respond_with_data(JS_RENDERED_PAGE, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    # Playwright executes JS — rendered text should be in the DOM
    assert ctx.page_html is not None
    assert "Rendered by JS" in ctx.page_html


@pytest.mark.asyncio
async def test_page_load_records_final_url(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/article").respond_with_data(SIMPLE_PAGE, content_type="text/html")

    url = httpserver.url_for("/article")
    ctx = ArchiveContext(url=url, config=_config())
    await run(ctx)

    assert ctx.final_url is not None
    assert "/article" in ctx.final_url


@pytest.mark.asyncio
async def test_page_load_logs_step(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/").respond_with_data(SIMPLE_PAGE, content_type="text/html")

    ctx = ArchiveContext(url=httpserver.url_for("/"), config=_config())
    await run(ctx)

    assert any("page_load" in entry for entry in ctx.step_log)


@pytest.mark.asyncio
async def test_page_load_404_raises(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/missing").respond_with_data("Not Found", status=404)

    ctx = ArchiveContext(url=httpserver.url_for("/missing"), config=_config())

    with pytest.raises(PageLoadError, match="HTTP 404"):
        await run(ctx)


@pytest.mark.asyncio
async def test_page_load_500_raises(httpserver: HTTPServer) -> None:
    httpserver.expect_request("/error").respond_with_data("Server Error", status=500)

    ctx = ArchiveContext(url=httpserver.url_for("/error"), config=_config())

    with pytest.raises(PageLoadError, match="HTTP 500"):
        await run(ctx)


@pytest.mark.asyncio
async def test_page_load_uses_configured_user_agent(httpserver: HTTPServer) -> None:
    received_ua: list[str] = []

    def handler(request: object) -> None:
        from werkzeug.wrappers import Request, Response

        assert isinstance(request, Request)
        received_ua.append(request.headers.get("User-Agent", ""))
        return Response(SIMPLE_PAGE, content_type="text/html")

    httpserver.expect_request("/ua-check").respond_with_handler(handler)

    config = _config()
    # Override to a known UA
    from archiveinator.config import UserAgent, UserAgentConfig

    config.user_agents = UserAgentConfig(
        agents=[UserAgent(name="test-bot", ua="TestBot/2.0", enabled=True)]
    )

    ctx = ArchiveContext(url=httpserver.url_for("/ua-check"), config=config)
    await run(ctx)

    assert received_ua, "Handler was not called"
    assert received_ua[0] == "TestBot/2.0"
