from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archiveinator.config import Config


@dataclass
class ArchiveContext:
    """Shared state passed through every pipeline step."""

    url: str
    config: Config
    # Populated by page_load
    page_html: str | None = None
    page_title: str | None = None
    final_url: str | None = None
    response_status: int | None = None
    # Populated by naming / output steps
    output_path: Path | None = None
    is_partial: bool = False
    # Paywall bypass state
    paywalled: bool = False
    paywall_reason: str | None = None
    bypass_method: str | None = None
    # Per-attempt overrides (set by bypass strategies before each page_load retry)
    ua_override: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    cookies: list[dict[str, Any]] = field(default_factory=list)
    use_stealth: bool = False
    # Diagnostics — steps append notes here
    step_log: list[str] = field(default_factory=list)

    def log(self, step: str, msg: str) -> None:
        self.step_log.append(f"[{step}] {msg}")
