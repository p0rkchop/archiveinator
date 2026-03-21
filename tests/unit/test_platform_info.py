from __future__ import annotations

import pytest
from pytest import MonkeyPatch

import archiveinator.platform_info as pi


def _patch_platform(monkeypatch: MonkeyPatch, system: str, machine: str) -> None:
    monkeypatch.setattr(pi.platform, "system", lambda: system)
    monkeypatch.setattr(pi.platform, "machine", lambda: machine)


def test_macos_apple_silicon(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Darwin", "arm64")
    assert pi.get_monolith_asset_name() == "monolith-darwin-aarch64"


def test_macos_apple_silicon_aarch64_alias(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Darwin", "aarch64")
    assert pi.get_monolith_asset_name() == "monolith-darwin-aarch64"


def test_macos_intel(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Darwin", "x86_64")
    assert pi.get_monolith_asset_name() == "monolith-darwin-x86_64"


def test_linux_x86_64(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Linux", "x86_64")
    assert pi.get_monolith_asset_name() == "monolith-linux-x86_64"


def test_linux_aarch64(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Linux", "aarch64")
    assert pi.get_monolith_asset_name() == "monolith-linux-aarch64"


def test_linux_arm64_alias(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Linux", "arm64")
    assert pi.get_monolith_asset_name() == "monolith-linux-aarch64"


def test_windows(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "Windows", "x86_64")
    assert pi.get_monolith_asset_name() == "monolith-windows-x86_64.exe"


def test_unsupported_platform_raises(monkeypatch: MonkeyPatch) -> None:
    _patch_platform(monkeypatch, "FreeBSD", "x86_64")
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        pi.get_monolith_asset_name()


def test_is_windows_true(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(pi.platform, "system", lambda: "Windows")
    assert pi.is_windows() is True


def test_is_windows_false(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(pi.platform, "system", lambda: "Darwin")
    assert pi.is_windows() is False
