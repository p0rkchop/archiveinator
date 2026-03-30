from __future__ import annotations

from pathlib import Path

import click
from pytest import MonkeyPatch
from typer.testing import CliRunner

from archiveinator.cli import app
from archiveinator.config import Config

runner = CliRunner()


def _plain(output: str) -> str:
    """Strip ANSI escape codes from CLI output."""
    return click.unstyle(output)


# --- Basic CLI shape ---


def test_archive_requires_url() -> None:
    result = runner.invoke(app, ["archive"])
    assert result.exit_code != 0


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "archive" in result.output
    assert "setup" in result.output


def test_archive_help() -> None:
    result = runner.invoke(app, ["archive", "--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "--output-dir" in output
    assert "--verbose" in output


def test_setup_help() -> None:
    result = runner.invoke(app, ["setup", "--help"])
    assert result.exit_code == 0


# --- Input validation ---


def test_archive_rejects_non_http_url(tmp_path: Path) -> None:
    result = runner.invoke(app, ["archive", "ftp://example.com"])
    assert result.exit_code == 1
    assert "Invalid URL" in result.output


def test_archive_invalid_output_dir(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["archive", "https://example.com", "--output-dir", str(tmp_path / "nonexistent")],
    )
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_archive_stdout_and_output_dir_are_mutually_exclusive(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["archive", "https://example.com", "--stdout", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


# --- Successful archive ---


def _mock_page_load(ctx: object) -> None:
    from archiveinator.pipeline import ArchiveContext

    assert isinstance(ctx, ArchiveContext)
    ctx.page_html = "<html><head><title>Test Page</title></head><body>hi</body></html>"
    ctx.page_title = "Test Page"
    ctx.final_url = "https://example.com/article"


async def _async_mock_page_load(ctx: object) -> None:
    _mock_page_load(ctx)


async def _async_noop(ctx: object) -> None:
    pass


def test_archive_success(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    result = runner.invoke(app, ["archive", "https://example.com", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1
    assert "_partial" not in html_files[0].name


def test_archive_success_filename_format(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    result = runner.invoke(
        app, ["archive", "https://example.com/article", "--output-dir", str(tmp_path)]
    )

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    name = html_files[0].name
    # Should contain hostname and title slug
    assert "example.com" in name
    assert "test-page" in name


# --- Retry logic ---


def test_archive_retries_once_on_page_load_failure(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod
    from archiveinator.steps.page_load import PageLoadError

    monkeypatch.setattr(ai_mod, "run", _async_noop)
    monkeypatch.setattr("archiveinator.cli._RETRY_DELAY_SECONDS", 0)

    call_count = [0]

    async def flaky_page_load(ctx: object) -> None:
        call_count[0] += 1
        if call_count[0] == 1:
            raise PageLoadError("HTTP 503")
        _mock_page_load(ctx)

    monkeypatch.setattr(pl_mod, "run", flaky_page_load)

    result = runner.invoke(app, ["archive", "https://example.com", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert call_count[0] == 2


def test_archive_fails_after_two_page_load_errors(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.page_load as pl_mod
    from archiveinator.steps.page_load import PageLoadError

    monkeypatch.setattr("archiveinator.cli._RETRY_DELAY_SECONDS", 0)

    async def always_fail(ctx: object) -> None:
        raise PageLoadError("HTTP 503")

    monkeypatch.setattr(pl_mod, "run", always_fail)

    result = runner.invoke(app, ["archive", "https://example.com", "--output-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "Failed to load page" in result.output


# --- Partial saves ---


def test_archive_partial_save_on_inlining_failure(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod
    from archiveinator.steps.asset_inlining import AssetInliningError

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load)

    async def inlining_fails(ctx: object) -> None:
        raise AssetInliningError("monolith not found")

    monkeypatch.setattr(ai_mod, "run", inlining_fails)

    result = runner.invoke(app, ["archive", "https://example.com", "--output-dir", str(tmp_path)])

    # Should succeed (exit 0) but save a _partial file
    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1
    assert "_partial" in html_files[0].name
    assert "Partial" in result.output


def test_archive_stdout_writes_html_to_output(monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    result = runner.invoke(app, ["archive", "https://example.com", "--stdout"])

    assert result.exit_code == 0
    assert "<html>" in result.output
    assert "Test Page" in result.output


def test_archive_stdout_does_not_create_files(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    runner.invoke(app, ["archive", "https://example.com", "--stdout"])

    # No file should be written to CWD or any path
    assert list(tmp_path.glob("*.html")) == []


def test_update_blocklists_command(monkeypatch: MonkeyPatch) -> None:
    import archiveinator.cli as cli_mod

    called = []
    monkeypatch.setattr(
        cli_mod,
        "_setup_blocklists",
        lambda ignore_cert_errors=False: called.append(True),
        raising=False,
    )

    # Patch at the import site inside the command
    import archiveinator.setup_cmd as setup_mod

    monkeypatch.setattr(
        setup_mod, "_setup_blocklists", lambda ignore_cert_errors=False: called.append(True)
    )

    result = runner.invoke(app, ["update-blocklists"])
    assert result.exit_code == 0
    assert called


# --- Paywall bypass ---


def _mock_page_load_paywalled(ctx: object) -> None:
    from archiveinator.pipeline import ArchiveContext

    assert isinstance(ctx, ArchiveContext)
    ctx.page_html = "<html><body><div class='paywall'>Subscribe</div><p>preview</p></body></html>"
    ctx.page_title = "Paywalled Article"
    ctx.final_url = "https://example.com/article"
    ctx.paywalled = True
    ctx.paywall_reason = "DOM selector matched: .paywall"


async def _async_mock_page_load_paywalled(ctx: object) -> None:
    _mock_page_load_paywalled(ctx)


def _make_config(tmp_path: Path, steps: list[str]) -> Config:
    """Build a Config with a specific pipeline — bypasses YAML file on disk."""
    from archiveinator.config import Config, PipelineStep

    cfg = Config()
    cfg.output_dir = tmp_path
    cfg.pipeline = [PipelineStep(step=s) for s in steps]
    return cfg


def test_paywall_detected_warning_shown(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """CLI warns when paywall is detected and all bypasses fail."""
    import archiveinator.cli as cli_mod
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load_paywalled)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    # Return a controlled config with no bypass strategies so none fire.
    # Mocking load_config avoids the YAML file on disk overriding the pipeline.
    cfg = _make_config(
        tmp_path,
        steps=["page_load", "paywall_detection", "asset_inlining"],
    )
    monkeypatch.setattr(cli_mod, "load_config", lambda: cfg)

    result = runner.invoke(app, ["archive", "https://example.com"])

    assert result.exit_code == 0
    assert "Paywall/block detected" in result.output
    assert "bypass strategies exhausted" in result.output


def test_paywall_bypass_via_content_extraction(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Content extraction fallback clears paywalled flag and saves a file."""
    import archiveinator.cli as cli_mod
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.content_extraction as ce_mod
    import archiveinator.steps.page_load as pl_mod

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load_paywalled)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    async def mock_content_extract(ctx: object) -> None:
        from archiveinator.pipeline import ArchiveContext

        assert isinstance(ctx, ArchiveContext)
        ctx.page_html = "<html><body><article>Extracted content</article></body></html>"
        ctx.paywalled = False
        ctx.bypass_method = "content_extraction"

    monkeypatch.setattr(ce_mod, "run", mock_content_extract)

    cfg = _make_config(
        tmp_path,
        steps=["page_load", "paywall_detection", "content_extraction", "asset_inlining"],
    )
    monkeypatch.setattr(cli_mod, "load_config", lambda: cfg)

    result = runner.invoke(app, ["archive", "https://example.com"])

    assert result.exit_code == 0
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1


def test_archive_partial_file_contains_page_html(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod
    from archiveinator.steps.asset_inlining import AssetInliningError

    monkeypatch.setattr(pl_mod, "run", _async_mock_page_load)

    async def inlining_fails(ctx: object) -> None:
        raise AssetInliningError("monolith not found")

    monkeypatch.setattr(ai_mod, "run", inlining_fails)

    runner.invoke(app, ["archive", "https://example.com", "--output-dir", str(tmp_path)])

    html_files = list(tmp_path.glob("*.html"))
    content = html_files[0].read_text()
    assert "Test Page" in content


# --- Cache subcommands ---


def test_cache_list_empty(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """cache list shows 'No cached entries' when the cache is empty."""
    monkeypatch.setattr("archiveinator.bypass_cache.CACHE_PATH", tmp_path / "bypass_cache.yaml")
    result = runner.invoke(app, ["cache", "list"])
    assert result.exit_code == 0
    assert "No cached entries" in result.output


def test_cache_list_with_entries(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """cache list shows entries in a table."""
    monkeypatch.setattr("archiveinator.bypass_cache.CACHE_PATH", tmp_path / "bypass_cache.yaml")
    from archiveinator.bypass_cache import record_success

    record_success("https://example.com/page", "header_tricks")
    record_success("https://news.site.org/article", "ua_cycling", ua_name="googlebot")

    result = runner.invoke(app, ["cache", "list"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "example.com" in output
    assert "header_tricks" in output
    assert "news.site.org" in output
    assert "ua_cycling" in output
    assert "googlebot" in output


def test_cache_clear_all(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """cache clear removes all entries."""
    monkeypatch.setattr("archiveinator.bypass_cache.CACHE_PATH", tmp_path / "bypass_cache.yaml")
    from archiveinator.bypass_cache import list_entries, record_success

    record_success("https://a.com/p", "ua_cycling")
    record_success("https://b.com/p", "header_tricks")
    assert len(list_entries()) == 2

    result = runner.invoke(app, ["cache", "clear"])
    assert result.exit_code == 0
    assert "Cleared 2 cache entry(ies)" in result.output
    assert len(list_entries()) == 0


def test_cache_clear_domain(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """cache clear --domain removes only the specified domain."""
    monkeypatch.setattr("archiveinator.bypass_cache.CACHE_PATH", tmp_path / "bypass_cache.yaml")
    from archiveinator.bypass_cache import list_entries, record_success

    record_success("https://a.com/p", "ua_cycling")
    record_success("https://b.com/p", "header_tricks")

    result = runner.invoke(app, ["cache", "clear", "--domain", "a.com"])
    assert result.exit_code == 0
    assert "Cleared cache entry for a.com" in result.output

    entries = list_entries()
    assert len(entries) == 1
    assert entries[0][0] == "b.com"


# --- Cookies ---


def test_archive_with_cookies_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """--cookies-file loads JSON cookies and passes them to page_load."""
    import json

    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    cookie_data = [
        {
            "name": "session",
            "value": "abc123",
            "domain": "example.com",
            "path": "/",
            "secure": True,
        }
    ]
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps(cookie_data))

    captured_cookies = []

    original_mock = _async_mock_page_load

    async def mock_page_load(ctx):
        captured_cookies.extend(ctx.cookies)
        await original_mock(ctx)

    monkeypatch.setattr(pl_mod, "run", mock_page_load)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    result = runner.invoke(
        app,
        [
            "archive",
            "https://example.com",
            "--cookies-file",
            str(cookie_file),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert len(captured_cookies) == 1
    assert captured_cookies[0]["name"] == "session"
    assert captured_cookies[0]["value"] == "abc123"


def test_archive_with_cookie_editor_format(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """--cookies-file loads Cookie-Editor format JSON."""
    import json

    import archiveinator.steps.asset_inlining as ai_mod
    import archiveinator.steps.page_load as pl_mod

    cookie_data = {
        "cookies": [
            {
                "name": "session",
                "value": "abc123",
                "domain": "example.com",
                "path": "/",
                "secure": True,
                "extraField": "should be stripped",
            }
        ]
    }
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps(cookie_data))

    captured_cookies = []

    original_mock = _async_mock_page_load

    async def mock_page_load(ctx):
        captured_cookies.extend(ctx.cookies)
        await original_mock(ctx)

    monkeypatch.setattr(pl_mod, "run", mock_page_load)
    monkeypatch.setattr(ai_mod, "run", _async_noop)

    result = runner.invoke(
        app,
        [
            "archive",
            "https://example.com",
            "--cookies-file",
            str(cookie_file),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert len(captured_cookies) == 1
    cookie = captured_cookies[0]
    assert cookie["name"] == "session"
    assert cookie["value"] == "abc123"
    assert cookie["domain"] == "example.com"
    assert cookie["path"] == "/"
    assert cookie["secure"]
    assert "extraField" not in cookie


def test_load_cookies_full_storage_format(tmp_path: Path) -> None:
    """_load_cookies extracts cookies from Playwright storage state format."""
    from archiveinator.cli import _load_cookies
    import json

    storage_state = {
        "cookies": [
            {
                "name": "session",
                "value": "abc123",
                "domain": "example.com",
                "path": "/",
                "secure": True,
            }
        ],
        "origins": []
    }
    cookie_file = tmp_path / "storage.json"
    cookie_file.write_text(json.dumps(storage_state))

    cookies = _load_cookies(str(cookie_file))
    assert len(cookies) == 1
    cookie = cookies[0]
    assert cookie["name"] == "session"
    assert cookie["value"] == "abc123"
    assert cookie["domain"] == "example.com"
    assert cookie["path"] == "/"
    assert cookie["secure"]
    assert "origins" not in cookie


# --- Login command ---


def test_login_command_help() -> None:
    """Basic help test for login command."""
    result = runner.invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "URL to open for login" in output
    assert "--output" in output
    assert "--headless" in output
    assert "--timeout" in output


def test_login_command_requires_url() -> None:
    """Login command requires URL argument."""
    result = runner.invoke(app, ["login"])
    assert result.exit_code != 0


def test_login_command_invalid_url() -> None:
    """Login command rejects non-http URLs."""
    result = runner.invoke(app, ["login", "ftp://example.com"])
    assert result.exit_code != 0
    assert "Invalid URL" in result.output


def test_login_command_with_output_option(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Login command respects --output option."""
    import json

    import archiveinator.cli as cli_mod

    captured_url = None
    captured_output = None
    captured_headless = None
    captured_timeout = None

    async def mock_capture_login(
        url: str, output: Path, headless: bool, timeout: int, full_storage: bool
    ) -> None:
        nonlocal captured_url, captured_output, captured_headless, captured_timeout
        captured_url = url
        captured_output = output
        captured_headless = headless
        captured_timeout = timeout
        # Write dummy cookies to output file
        with open(output, "w") as f:
            json.dump({"cookies": []}, f)

    monkeypatch.setattr(cli_mod, "_capture_login", mock_capture_login)

    output_file = tmp_path / "mycookies.json"
    result = runner.invoke(
        app,
        [
            "login",
            "https://example.com",
            "--output",
            str(output_file),
            "--headless",
            "--timeout",
            "60",
        ],
    )
    assert result.exit_code == 0
    assert captured_url == "https://example.com"
    assert captured_output == output_file
    assert captured_headless is True
    assert captured_timeout == 60
    assert output_file.exists()
    # Verify file contains valid JSON
    data = json.loads(output_file.read_text())
    assert "cookies" in data


def test_login_command_full_storage(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Login command with --full-storage saves storage state."""
    import json

    import archiveinator.cli as cli_mod

    captured_full_storage = None

    async def mock_capture_login(
        url: str, output: Path, headless: bool, timeout: int, full_storage: bool
    ) -> None:
        nonlocal captured_full_storage
        captured_full_storage = full_storage
        # Write dummy storage state
        with open(output, "w") as f:
            json.dump({"cookies": [], "origins": []}, f)

    monkeypatch.setattr(cli_mod, "_capture_login", mock_capture_login)

    output_file = tmp_path / "storage.json"
    result = runner.invoke(
        app,
        [
            "login",
            "https://example.com",
            "--output",
            str(output_file),
            "--full-storage",
        ],
    )
    assert result.exit_code == 0
    assert captured_full_storage is True
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert "cookies" in data
    assert "origins" in data
