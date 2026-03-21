from __future__ import annotations

import platform


def get_monolith_asset_name() -> str:
    """Return the GitHub release asset filename for the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "monolith-darwin-aarch64"
        return "monolith-darwin-x86_64"
    elif system == "linux":
        if machine in ("arm64", "aarch64"):
            return "monolith-linux-aarch64"
        return "monolith-linux-x86_64"
    elif system == "windows":
        return "monolith-windows-x86_64.exe"
    else:
        raise RuntimeError(f"Unsupported platform: {system}/{machine}")


def is_windows() -> bool:
    return platform.system().lower() == "windows"
