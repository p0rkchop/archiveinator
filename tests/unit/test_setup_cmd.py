from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

import archiveinator.setup_cmd as setup_mod
from archiveinator.setup_cmd import SetupError, _find_monolith_in_path


def _fake_release(asset_names: list[str]) -> dict:
    return {
        "tag_name": "v2.10.1",
        "assets": [
            {"name": n, "browser_download_url": f"https://example.com/releases/{n}"}
            for n in asset_names
        ],
    }


# --- _find_monolith_in_path ---


def test_find_monolith_in_path_found(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    bin_path = tmp_path / "monolith"
    bin_path.touch()
    monkeypatch.setattr("shutil.which", lambda name: str(bin_path))
    result = _find_monolith_in_path()
    assert result == bin_path


def test_find_monolith_in_path_not_found(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert _find_monolith_in_path() is None


# --- _setup_monolith ---


def test_setup_monolith_skips_if_already_installed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "monolith"
    dest.touch()
    monkeypatch.setattr(setup_mod, "monolith_bin", lambda: dest)

    download_called = []
    monkeypatch.setattr(
        setup_mod,
        "_download_monolith_binary",
        lambda ignore_cert_errors=False: download_called.append(True),
    )

    setup_mod._setup_monolith()
    assert not download_called


def test_setup_monolith_copies_from_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / "bin" / "monolith"
    dest.parent.mkdir()
    src = tmp_path / "monolith_src"
    src.write_bytes(b"fake binary")

    monkeypatch.setattr(setup_mod, "monolith_bin", lambda: dest)
    monkeypatch.setattr(setup_mod, "_find_monolith_in_path", lambda: src)
    monkeypatch.setattr(setup_mod, "is_windows", lambda: False)

    setup_mod._setup_monolith()

    assert dest.exists()
    assert dest.read_bytes() == b"fake binary"
    assert dest.stat().st_mode & stat.S_IXUSR


def test_setup_monolith_downloads_when_not_in_path(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "monolith"
    monkeypatch.setattr(setup_mod, "monolith_bin", lambda: dest)
    monkeypatch.setattr(setup_mod, "_find_monolith_in_path", lambda: None)

    download_called = []
    monkeypatch.setattr(
        setup_mod,
        "_download_monolith_binary",
        lambda ignore_cert_errors=False: download_called.append(True),
    )

    setup_mod._setup_monolith()
    assert download_called


# --- _download_monolith_binary ---


def test_download_raises_when_asset_not_in_release(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(setup_mod, "get_monolith_asset_name", lambda: "archiveinator-linux-x86_64")

    mock_resp = MagicMock()
    mock_resp.json.return_value = _fake_release(["other-asset"])
    mock_resp.raise_for_status = lambda: None

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: mock_resp)

    with pytest.raises(SetupError, match="not found in latest archiveinator release"):
        setup_mod._download_monolith_binary()


def test_download_success(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / "monolith"
    monkeypatch.setattr(setup_mod, "monolith_bin", lambda: dest)
    monkeypatch.setattr(setup_mod, "get_monolith_asset_name", lambda: "archiveinator-linux-x86_64")
    monkeypatch.setattr(setup_mod, "is_windows", lambda: False)

    mock_resp = MagicMock()
    mock_resp.json.return_value = _fake_release(["archiveinator-linux-x86_64"])
    mock_resp.raise_for_status = lambda: None

    fake_binary = b"\x7fELF fake binary"

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: mock_resp)

    mock_stream_resp = MagicMock()
    mock_stream_resp.raise_for_status = lambda: None
    mock_stream_resp.iter_bytes.return_value = [fake_binary]
    mock_stream_resp.__enter__ = lambda s: s
    mock_stream_resp.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: mock_stream_resp)

    setup_mod._download_monolith_binary()

    assert dest.exists()
    assert dest.read_bytes() == fake_binary
    assert dest.stat().st_mode & stat.S_IXUSR


# --- _setup_blocklists ---


def test_blocklist_download_failure_is_non_fatal(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    import httpx

    monkeypatch.setattr(setup_mod, "easylist_path", lambda: tmp_path / "easylist.txt")
    monkeypatch.setattr(setup_mod, "easyprivacy_path", lambda: tmp_path / "easyprivacy.txt")
    monkeypatch.setattr(httpx, "get", MagicMock(side_effect=httpx.NetworkError("offline")))

    # Should not raise — just warn
    setup_mod._setup_blocklists()


# --- run (full setup) ---


def test_run_creates_config_if_missing(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr(setup_mod, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(setup_mod, "config_path", lambda: config_file)
    monkeypatch.setattr(
        setup_mod, "_install_playwright_chromium", lambda ignore_cert_errors=False: None
    )
    monkeypatch.setattr(setup_mod, "_setup_monolith", lambda ignore_cert_errors=False: None)
    monkeypatch.setattr(setup_mod, "_setup_blocklists", lambda ignore_cert_errors=False: None)

    from archiveinator import config as config_mod

    monkeypatch.setattr(config_mod, "CONFIG_PATH", config_file)

    setup_mod.run()
    assert config_file.exists()


def test_run_preserves_existing_config(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("timeout_seconds: 99\n")
    monkeypatch.setattr(setup_mod, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(setup_mod, "config_path", lambda: config_file)
    monkeypatch.setattr(
        setup_mod, "_install_playwright_chromium", lambda ignore_cert_errors=False: None
    )
    monkeypatch.setattr(setup_mod, "_setup_monolith", lambda ignore_cert_errors=False: None)
    monkeypatch.setattr(setup_mod, "_setup_blocklists", lambda ignore_cert_errors=False: None)

    setup_mod.run()
    assert "timeout_seconds: 99" in config_file.read_text()
