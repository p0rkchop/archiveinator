from __future__ import annotations

import platform


def get_monolith_asset_name() -> str:
    """Return the GitHub release asset filename for the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "archiveinator-darwin-aarch64"
        return "archiveinator-darwin-x86_64"
    elif system == "linux":
        if machine in ("arm64", "aarch64"):
            return "archiveinator-linux-aarch64"
        return "archiveinator-linux-x86_64"
    else:
        raise RuntimeError(f"Unsupported platform: {system}/{machine}")
