from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from archiveinator.cli import app

runner = CliRunner(env={"NO_COLOR": "1"})


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
    assert "--output-dir" in result.output
    assert "--verbose" in result.output


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
