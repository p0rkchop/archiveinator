from __future__ import annotations

import os
import shutil
import ssl
import stat
import subprocess
import sys
from pathlib import Path

import httpx

from archiveinator import console
from archiveinator.blocklist import easylist_path, easyprivacy_path
from archiveinator.config import DATA_DIR, config_path, create_default, monolith_bin
from archiveinator.platform_info import get_monolith_asset_name, is_windows

ARCHIVEINATOR_RELEASES_API = "https://api.github.com/repos/p0rkchop/archiveinator/releases/latest"


class SetupError(Exception):
    pass


def _ensure_dirs() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    monolith_bin().parent.mkdir(parents=True, exist_ok=True)


def _install_playwright_chromium(ignore_cert_errors: bool = False) -> None:
    console.info("Installing Playwright Chromium...")
    env = os.environ.copy()
    if ignore_cert_errors:
        env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
        console.info("Certificate validation disabled for Playwright installation")

    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode == 0:
        console.success("Playwright Chromium installed")
        return

    # Check for SSL certificate error
    if "UNABLE_TO_GET_ISSUER_CERT_LOCALLY" in result.stderr:
        if ignore_cert_errors:
            raise SetupError(
                "Playwright Chromium installation failed due to SSL certificate error even with NODE_TLS_REJECT_UNAUTHORIZED=0"
            )
        else:
            # Automatic fallback: retry with certificate validation disabled
            console.warning(
                "SSL certificate error detected, retrying with certificate validation disabled..."
            )
            env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode == 0:
                console.success(
                    "Playwright Chromium installed (with certificate validation disabled)"
                )
                return
            # If still fails, raise error with suggestion
            raise SetupError(
                "Playwright Chromium installation failed due to SSL certificate error even after disabling validation.\n"
                "If you are behind a corporate proxy or have custom certificates, check your network configuration."
            )

    # Other errors
    raise SetupError(f"Failed to install Playwright Chromium: {result.stderr}")


def _find_monolith_in_path() -> Path | None:
    """Check if monolith is already available in PATH."""
    found = shutil.which("monolith")
    return Path(found) if found else None


def _download_monolith_binary(ignore_cert_errors: bool = False) -> None:
    """Download the monolith binary from archiveinator GitHub releases."""
    our_asset = get_monolith_asset_name()

    def _fetch_release_info() -> httpx.Response:
        if ignore_cert_errors:
            console.info("Certificate validation disabled, using verify=False...")
            resp = httpx.get(
                ARCHIVEINATOR_RELEASES_API, follow_redirects=True, timeout=30, verify=False
            )
            resp.raise_for_status()
            return resp

        try:
            resp = httpx.get(ARCHIVEINATOR_RELEASES_API, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            if isinstance(exc.__cause__, ssl.SSLCertVerificationError):
                console.warning("SSL certificate error detected, retrying with verify=False...")
                resp = httpx.get(
                    ARCHIVEINATOR_RELEASES_API, follow_redirects=True, timeout=30, verify=False
                )
                resp.raise_for_status()
                return resp
            raise

    console.info("Fetching archiveinator release info...")
    try:
        resp = _fetch_release_info()
    except httpx.HTTPError as exc:
        raise SetupError(f"Failed to fetch release info: {exc}") from exc

    release = resp.json()
    asset_url = next(
        (a["browser_download_url"] for a in release.get("assets", []) if a["name"] == our_asset),
        None,
    )
    if not asset_url:
        raise SetupError(
            f"Asset '{our_asset}' not found in latest archiveinator release.\n"
            "On macOS, install monolith via Homebrew:  brew install monolith"
        )

    console.info(f"Downloading monolith {release['tag_name']}...")
    if ignore_cert_errors:
        console.info("Certificate validation disabled, using verify=False...")
        try:
            with httpx.stream(
                "GET", asset_url, follow_redirects=True, timeout=60, verify=False
            ) as stream:
                stream.raise_for_status()
                dest = monolith_bin()
                with open(dest, "wb") as f:
                    for chunk in stream.iter_bytes():
                        f.write(chunk)
        except httpx.HTTPError as exc:
            raise SetupError(f"Failed to download monolith binary: {exc}") from exc
    else:
        try:
            with httpx.stream("GET", asset_url, follow_redirects=True, timeout=60) as stream:
                stream.raise_for_status()
                dest = monolith_bin()
                with open(dest, "wb") as f:
                    for chunk in stream.iter_bytes():
                        f.write(chunk)
        except httpx.HTTPError as exc:
            if isinstance(exc.__cause__, ssl.SSLCertVerificationError):
                console.warning("SSL certificate error detected, retrying with verify=False...")
                try:
                    with httpx.stream(
                        "GET", asset_url, follow_redirects=True, timeout=60, verify=False
                    ) as stream:
                        stream.raise_for_status()
                        dest = monolith_bin()
                        with open(dest, "wb") as f:
                            for chunk in stream.iter_bytes():
                                f.write(chunk)
                except httpx.HTTPError as exc2:
                    raise SetupError(
                        f"Failed to download monolith binary even with verify=False: {exc2}"
                    ) from exc2
            else:
                raise SetupError(f"Failed to download monolith binary: {exc}") from exc

    if not is_windows():
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    console.success(f"monolith installed to {monolith_bin()}")


def _setup_monolith(ignore_cert_errors: bool = False) -> None:
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

    _download_monolith_binary(ignore_cert_errors)


def _download_blocklist(name: str, url: str, dest: Path, ignore_cert_errors: bool = False) -> None:
    console.info(f"Downloading {name}...")
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=60)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        line_count = resp.text.count("\n")
        console.success(f"{name} downloaded ({line_count:,} rules)")
    except httpx.HTTPError as exc:
        if ignore_cert_errors and isinstance(exc.__cause__, ssl.SSLCertVerificationError):
            console.warning(
                f"SSL certificate error downloading {name}, retrying with verify=False..."
            )
            try:
                resp = httpx.get(url, follow_redirects=True, timeout=60, verify=False)
                resp.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                line_count = resp.text.count("\n")
                console.success(f"{name} downloaded with verify=False ({line_count:,} rules)")
                return
            except httpx.HTTPError as exc2:
                console.warning(
                    f"Could not download {name} even with verify=False: {exc2}. Built-in rules will be used."
                )
        else:
            if isinstance(exc.__cause__, ssl.SSLCertVerificationError):
                console.warning(
                    f"SSL certificate error downloading {name}, retrying with verify=False..."
                )
                try:
                    resp = httpx.get(url, follow_redirects=True, timeout=60, verify=False)
                    resp.raise_for_status()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(resp.content)
                    line_count = resp.text.count("\n")
                    console.success(f"{name} downloaded with verify=False ({line_count:,} rules)")
                    return
                except httpx.HTTPError as exc2:
                    console.warning(
                        f"Could not download {name} even with verify=False: {exc2}. Built-in rules will be used."
                    )
            else:
                console.warning(f"Could not download {name}: {exc}. Built-in rules will be used.")


def _setup_blocklists(ignore_cert_errors: bool = False) -> None:
    _download_blocklist(
        "EasyList",
        "https://easylist.to/easylist/easylist.txt",
        easylist_path(),
        ignore_cert_errors,
    )
    _download_blocklist(
        "EasyPrivacy",
        "https://easylist.to/easylist/easyprivacy.txt",
        easyprivacy_path(),
        ignore_cert_errors,
    )


def run(ignore_cert_errors: bool = False) -> None:
    """Run the full setup sequence."""
    console.info("Setting up archiveinator...")

    _ensure_dirs()

    if not config_path().exists():
        create_default(config_path())
        console.success(f"Config created at {config_path()}")
    else:
        console.success(f"Config already exists at {config_path()}")

    _install_playwright_chromium(ignore_cert_errors)
    _setup_monolith(ignore_cert_errors)
    _setup_blocklists(ignore_cert_errors)

    console.success("Setup complete. Run 'archiveinator archive <url>' to get started.")
