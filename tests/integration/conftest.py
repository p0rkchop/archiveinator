"""Integration test configuration: auto-skip when Playwright Chromium is absent."""

from __future__ import annotations

import subprocess

import pytest


def _chromium_installed() -> bool:
    """Check if Playwright Chromium is installed without importing Playwright."""
    try:
        result = subprocess.run(
            ["playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # No output means browser is already installed
        return result.returncode == 0 and not result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(autouse=True)
def _skip_without_chromium() -> None:
    """Auto-skip integration tests when Playwright Chromium is not installed."""
    if not _chromium_installed():
        pytest.skip("Playwright Chromium not installed — run 'archiveinator setup'")
