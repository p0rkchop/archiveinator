"""Per-domain bypass strategy cache.

Remembers which bypass strategy worked for a given domain so subsequent
visits can skip straight to the known-good approach.  Falls back to the
full strategy suite when the cached strategy fails.

Subsumes the older ``ua_manager.ua_cache.yaml`` — entries now live in
``bypass_cache.yaml`` and can store any strategy, not just UAs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import yaml

from archiveinator.config import CONFIG_DIR

CACHE_PATH = CONFIG_DIR / "bypass_cache.yaml"

# Entries older than this (days) without a success are pruned on load.
_MAX_AGE_DAYS = 90

# After this many consecutive failures, demote the cached strategy.
_MAX_CONSECUTIVE_FAILURES = 3


@dataclass
class CacheEntry:
    """A single domain's bypass history."""

    strategy: str
    ua_name: str | None = None
    last_success: str = ""
    attempts: int = 0
    successes: int = 0
    consecutive_failures: int = 0


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _load_raw() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _save_raw(data: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def _prune(data: dict[str, Any]) -> dict[str, Any]:
    """Remove stale entries that haven't succeeded recently."""
    now = datetime.now(tz=UTC)
    pruned: dict[str, Any] = {}
    for domain, entry in data.items():
        last = entry.get("last_success", "")
        if last:
            try:
                age = (now - datetime.fromisoformat(last)).days
                if age <= _MAX_AGE_DAYS:
                    pruned[domain] = entry
            except (ValueError, TypeError):
                pass
        else:
            # No last_success — keep only if few failures (newly cached, not yet proven)
            if entry.get("consecutive_failures", 0) < _MAX_CONSECUTIVE_FAILURES:
                pruned[domain] = entry
    return pruned


def lookup(url: str) -> CacheEntry | None:
    """Return the cached bypass strategy for this domain, if any."""
    data = _prune(_load_raw())
    domain = _domain(url)
    entry = data.get(domain)
    if entry is None:
        return None
    # Demoted entries (too many consecutive failures) are skipped
    if entry.get("consecutive_failures", 0) >= _MAX_CONSECUTIVE_FAILURES:
        return None
    return CacheEntry(
        strategy=entry["strategy"],
        ua_name=entry.get("ua_name"),
        last_success=entry.get("last_success", ""),
        attempts=entry.get("attempts", 0),
        successes=entry.get("successes", 0),
        consecutive_failures=entry.get("consecutive_failures", 0),
    )


def record_success(url: str, strategy: str, ua_name: str | None = None) -> None:
    """Record a successful bypass for this domain."""
    data = _load_raw()
    domain = _domain(url)
    existing = data.get(domain, {})
    data[domain] = {
        "strategy": strategy,
        "ua_name": ua_name,
        "last_success": datetime.now(tz=UTC).isoformat(),
        "attempts": existing.get("attempts", 0) + 1,
        "successes": existing.get("successes", 0) + 1,
        "consecutive_failures": 0,
    }
    _save_raw(data)


def record_failure(url: str) -> None:
    """Record a failed bypass attempt for this domain."""
    data = _load_raw()
    domain = _domain(url)
    existing = data.get(domain, {})
    if not existing:
        return  # No cache entry to update
    existing["attempts"] = existing.get("attempts", 0) + 1
    existing["consecutive_failures"] = existing.get("consecutive_failures", 0) + 1
    data[domain] = existing
    _save_raw(data)


def clear(domain: str | None = None) -> int:
    """Clear cache entries. If domain is given, clear only that entry.

    Returns the number of entries removed.
    """
    if domain is None:
        data = _load_raw()
        count = len(data)
        _save_raw({})
        return count
    data = _load_raw()
    if domain in data:
        del data[domain]
        _save_raw(data)
        return 1
    return 0


def list_entries() -> list[tuple[str, CacheEntry]]:
    """Return all cache entries as (domain, CacheEntry) pairs."""
    data = _prune(_load_raw())
    results: list[tuple[str, CacheEntry]] = []
    for domain, entry in sorted(data.items()):
        results.append((
            domain,
            CacheEntry(
                strategy=entry["strategy"],
                ua_name=entry.get("ua_name"),
                last_success=entry.get("last_success", ""),
                attempts=entry.get("attempts", 0),
                successes=entry.get("successes", 0),
                consecutive_failures=entry.get("consecutive_failures", 0),
            ),
        ))
    return results
