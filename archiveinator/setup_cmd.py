from __future__ import annotations

import shutil
import stat
import subprocess
import sys
from pathlib import Path

import httpx

from archiveinator import console
from archiveinator.blocklist import easylist_path, easyprivacy_path
from archiveinator.config import CONFIG_PATH, DATA_DIR, create_default, monolith_bin
from archiveinator.platform_info import get_monolith_asset_name, is_windows

MONOLITH_RELEASES_API = "https://api.github.com/repos/Y2Z/monolith/releases/latest"

# Maps our platform asset names → Y2Z/monolith release asset names
_UPSTREAM_ASSET_MAP: dict[str, str] = {
    "monolith-linux-x86_64": "monolith-gnu-linux-x86_64",
    "monolith-linux-aarch64": "monolith-gnu-linux-aarch64",
    "monolith-windows-x86_64.exe": "monolith.exe",
    # macOS binaries are not published upstream — handled via PATH check
}


class SetupError(Exception):
    pass


def _ensure_dirs() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    monolith_bin().parent.mkdir(parents=True, exist_ok=True)


def _install_playwright_chromium() -> None:
    console.info("Installing Playwright Chromium...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=False,
    )
    if result.returncode != 0:
        raise SetupError("Failed to install Playwright Chromium")
    console.success("Playwright Chromium installed")


def _find_monolith_in_path() -> Path | None:
    """Check if monolith is already available in PATH."""
    found = shutil.which("monolith")
    return Path(found) if found else None


def _download_monolith_binary() -> None:
    """Download the monolith binary from GitHub releases to our data dir."""
    our_asset = get_monolith_asset_name()
    upstream_asset = _UPSTREAM_ASSET_MAP.get(our_asset)

    if upstream_asset is None:
        raise SetupError(
            f"No upstream monolith binary available for this platform ({our_asset}).\n"
            "On macOS, install via Homebrew:  brew install monolith"
        )

    console.info("Fetching monolith release info...")
    try:
        resp = httpx.get(MONOLITH_RELEASES_API, follow_redirects=True, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SetupError(f"Failed to fetch monolith release info: {exc}") from exc

    release = resp.json()
    asset_url = next(
        (
            a["browser_download_url"]
            for a in release.get("assets", [])
            if a["name"] == upstream_asset
        ),
        None,
    )
    if not asset_url:
        raise SetupError(
            f"Asset '{upstream_asset}' not found in latest monolith release. "
            "Check https://github.com/Y2Z/monolith/releases"
        )

    console.info(f"Downloading monolith {release['tag_name']}...")
    try:
        with httpx.stream("GET", asset_url, follow_redirects=True, timeout=60) as stream:
            stream.raise_for_status()
            dest = monolith_bin()
            with open(dest, "wb") as f:
                for chunk in stream.iter_bytes():
                    f.write(chunk)
    except httpx.HTTPError as exc:
        raise SetupError(f"Failed to download monolith binary: {exc}") from exc

    if not is_windows():
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    console.success(f"monolith installed to {monolith_bin()}")


def _setup_monolith() -> None:
    dest = monolith_bin()

    if dest.exists():
        console.success(f"monolith already installed at {dest}")
        return

    # Check PATH first (e.g., brew install monolith on macOS)
    path_bin = _find_monolith_in_path()
    if path_bin:
        shutil.copy2(path_bin, dest)
        if not is_windows():
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        console.success(f"monolith copied from {path_bin} to {dest}")
        return

    _download_monolith_binary()


def _download_blocklist(name: str, url: str, dest: Path) -> None:
    console.info(f"Downloading {name}...")
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=60)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        line_count = resp.text.count("\n")
        console.success(f"{name} downloaded ({line_count:,} rules)")
    except httpx.HTTPError as exc:
        console.warning(f"Could not download {name}: {exc}. Built-in rules will be used.")


def _setup_blocklists() -> None:
    _download_blocklist(
        "EasyList",
        "https://easylist.to/easylist/easylist.txt",
        easylist_path(),
    )
    _download_blocklist(
        "EasyPrivacy",
        "https://easylist.to/easylist/easyprivacy.txt",
        easyprivacy_path(),
    )


def run() -> None:
    """Run the full setup sequence."""
    console.info("Setting up archiveinator...")

    _ensure_dirs()

    if not CONFIG_PATH.exists():
        create_default(CONFIG_PATH)
        console.success(f"Config created at {CONFIG_PATH}")
    else:
        console.success(f"Config already exists at {CONFIG_PATH}")

    _install_playwright_chromium()
    _setup_monolith()
    _setup_blocklists()

    console.success("Setup complete. Run 'archiveinator archive <url>' to get started.")
