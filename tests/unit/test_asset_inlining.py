from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from archiveinator.config import Config
from archiveinator.pipeline import ArchiveContext
from archiveinator.steps.asset_inlining import AssetInliningError, check_monolith, run


def _ctx(html: str = "<html><body>test</body></html>") -> ArchiveContext:
    config = Config()
    config.timeout_seconds = 10
    ctx = ArchiveContext(url="https://example.com", config=config)
    ctx.page_html = html
    ctx.final_url = "https://example.com/article"
    return ctx


# --- check_monolith ---


def test_check_monolith_raises_when_missing(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: tmp_path / "monolith")
    with pytest.raises(AssetInliningError, match="archiveinator setup"):
        check_monolith()


def test_check_monolith_returns_path_when_present(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: bin_path)
    assert check_monolith() == bin_path


# --- run ---


@pytest.mark.asyncio
async def test_run_raises_when_no_page_html() -> None:
    ctx = _ctx()
    ctx.page_html = None
    with pytest.raises(AssetInliningError, match="No page HTML"):
        await run(ctx)


@pytest.mark.asyncio
async def test_run_raises_when_monolith_missing(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: tmp_path / "monolith")
    with pytest.raises(AssetInliningError, match="archiveinator setup"):
        await run(_ctx())


@pytest.mark.asyncio
async def test_run_success(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Mock subprocess.run to simulate a successful monolith invocation."""
    import archiveinator.steps.asset_inlining as ai_mod

    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: bin_path)

    inlined_html = "<html><head></head><body>inlined content</body></html>"

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        # Write fake output to the output file argument
        out_file = Path(cmd[cmd.index("-o") + 1])
        out_file.write_text(inlined_html, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ctx = _ctx()
    await run(ctx)

    assert ctx.page_html == inlined_html
    assert any("asset_inlining" in entry for entry in ctx.step_log)


@pytest.mark.asyncio
async def test_run_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: bin_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout=b"", stderr=b"something went wrong"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AssetInliningError, match="monolith exited 1"):
        await run(_ctx())


@pytest.mark.asyncio
async def test_run_raises_on_timeout(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: bin_path)

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd, timeout=20)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AssetInliningError, match="timed out"):
        await run(_ctx())


@pytest.mark.asyncio
async def test_run_passes_base_url_to_monolith(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: bin_path)

    captured_cmd: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured_cmd.append(cmd)
        out_file = Path(cmd[cmd.index("-o") + 1])
        out_file.write_text("<html></html>", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ctx = _ctx()
    ctx.final_url = "https://example.com/article"
    await run(ctx)

    assert "--base-url" in captured_cmd[0]
    base_url_idx = captured_cmd[0].index("--base-url")
    assert captured_cmd[0][base_url_idx + 1] == "https://example.com/article"


@pytest.mark.asyncio
async def test_run_uses_ctx_url_when_no_final_url(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import archiveinator.steps.asset_inlining as ai_mod

    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr(ai_mod, "monolith_bin", lambda: bin_path)

    captured_cmd: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured_cmd.append(cmd)
        out_file = Path(cmd[cmd.index("-o") + 1])
        out_file.write_text("<html></html>", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ctx = _ctx()
    ctx.final_url = None
    await run(ctx)

    base_url_idx = captured_cmd[0].index("--base-url")
    assert captured_cmd[0][base_url_idx + 1] == "https://example.com"
