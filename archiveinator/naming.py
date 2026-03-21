from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

TITLE_MAX_LEN = 80


def _slugify(text: str) -> str:
    """Convert arbitrary text to a filename-safe slug."""
    text = text.lower().strip()
    # Replace any whitespace or separator chars with a hyphen
    text = re.sub(r"[\s_/\\]+", "-", text)
    # Remove anything that isn't alphanumeric or a hyphen
    text = re.sub(r"[^\w-]", "", text)
    # Collapse runs of hyphens
    text = re.sub(r"-{2,}", "-", text)
    # Strip leading/trailing hyphens
    return text.strip("-")


def _extract_hostname(url: str) -> str:
    """Extract and normalise the hostname from a URL."""
    hostname = urlparse(url).hostname or "unknown"
    # Strip leading www.
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _truncate(text: str, max_len: int = TITLE_MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Don't cut mid-word — walk back to the last hyphen
    last_hyphen = truncated.rfind("-")
    if last_hyphen > max_len // 2:
        truncated = truncated[:last_hyphen]
    return truncated.strip("-")


def build_filename(
    url: str,
    title: str,
    ts: datetime | None = None,
    partial: bool = False,
) -> str:
    """
    Build the output filename.

    Format: YYYY-MM-DD_HH-MM_hostname_articleTitle.html
    Partial saves append '_partial' before the extension.
    """
    if ts is None:
        ts = datetime.now()

    date_part = ts.strftime("%Y-%m-%d_%H-%M")
    hostname = _extract_hostname(url)
    slug = _truncate(_slugify(title)) if title.strip() else "untitled"

    name = f"{date_part}_{hostname}_{slug}"
    suffix = "_partial" if partial else ""
    return f"{name}{suffix}.html"
