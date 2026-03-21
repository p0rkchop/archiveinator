from __future__ import annotations

from pathlib import Path

import adblock

from archiveinator.config import data_dir

# Minimal built-in fallback rules — used when the full EasyList hasn't been
# downloaded yet (before `archiveinator setup` is run).
_BUILTIN_RULES = [
    "||doubleclick.net^",
    "||googlesyndication.com^",
    "||googleadservices.com^",
    "||adnxs.com^",
    "||amazon-adsystem.com^",
    "||scorecardresearch.com^",
    "||outbrain.com^",
    "||taboola.com^",
    "||moatads.com^",
    "||adsafeprotected.com^",
    "||rubiconproject.com^",
    "||pubmatic.com^",
    "||openx.net^",
    "||advertising.com^",
    "||ads.twitter.com^",
    "||facebook.com/tr^",
    "||quantserve.com^",
    "||chartbeat.com^",
]

_EASYLIST_PATH = data_dir() / "easylist.txt"
_EASYPRIVACY_PATH = data_dir() / "easyprivacy.txt"


def _build_engine(rules: list[str]) -> adblock.Engine:
    fs = adblock.FilterSet()
    fs.add_filters(rules)
    return adblock.Engine(fs)


def load_engine() -> adblock.Engine:
    """
    Load the adblock engine from cached EasyList files.
    Falls back to built-in rules if the files haven't been downloaded yet.
    """
    rules: list[str] = []

    for path in (_EASYLIST_PATH, _EASYPRIVACY_PATH):
        if path.exists():
            rules.extend(_read_filter_file(path))

    if not rules:
        rules = _BUILTIN_RULES

    return _build_engine(rules)


def _read_filter_file(path: Path) -> list[str]:
    """Read an Adblock Plus filter file, skipping comments and blank lines."""
    lines = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("!") and not line.startswith("["):
            lines.append(line)
    return lines


def should_block(
    engine: adblock.Engine,
    url: str,
    source_url: str,
    resource_type: str = "other",
) -> bool:
    """Return True if the request should be blocked."""
    try:
        result = engine.check_network_urls(url, source_url, resource_type)
        return result.matched
    except Exception:
        return False


def easylist_path() -> Path:
    return _EASYLIST_PATH


def easyprivacy_path() -> Path:
    return _EASYPRIVACY_PATH
