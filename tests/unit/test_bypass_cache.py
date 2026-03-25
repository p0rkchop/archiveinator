from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from archiveinator.bypass_cache import (
    clear,
    list_entries,
    lookup,
    record_failure,
    record_success,
)


@pytest.fixture(autouse=True)
def _patch_cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the bypass cache to a temp file for every test."""
    monkeypatch.setattr("archiveinator.bypass_cache.CACHE_PATH", tmp_path / "bypass_cache.yaml")


def test_lookup_returns_none_when_empty():
    assert lookup("https://example.com/article") is None


def test_record_success_then_lookup():
    url = "https://example.com/article"
    record_success(url, "header_tricks")
    entry = lookup(url)
    assert entry is not None
    assert entry.strategy == "header_tricks"
    assert entry.attempts == 1
    assert entry.successes == 1
    assert entry.consecutive_failures == 0


def test_record_success_stores_ua_name():
    url = "https://example.com/page"
    record_success(url, "ua_cycling", ua_name="googlebot")
    entry = lookup(url)
    assert entry is not None
    assert entry.ua_name == "googlebot"


def test_record_failure_increments_counters():
    url = "https://example.com/page"
    record_success(url, "header_tricks")
    record_failure(url)
    entry = lookup(url)
    assert entry is not None
    assert entry.consecutive_failures == 1
    assert entry.attempts == 2  # 1 success + 1 failure


def test_record_failure_noop_when_no_entry():
    """Failure on an unknown domain should not create an entry."""
    record_failure("https://unknown.com/page")
    assert lookup("https://unknown.com/page") is None


def test_consecutive_failures_demote_entry():
    url = "https://example.com/page"
    record_success(url, "ua_cycling")
    for _ in range(3):
        record_failure(url)
    # After 3 consecutive failures, lookup should return None (demoted)
    assert lookup(url) is None


def test_success_resets_consecutive_failures():
    url = "https://example.com/page"
    record_success(url, "ua_cycling")
    record_failure(url)
    record_failure(url)
    # 2 failures — not yet demoted
    assert lookup(url) is not None
    # Success resets counter
    record_success(url, "header_tricks")
    entry = lookup(url)
    assert entry is not None
    assert entry.consecutive_failures == 0
    assert entry.strategy == "header_tricks"


def test_lookup_uses_domain_not_full_url():
    record_success("https://example.com/article-1", "header_tricks")
    entry = lookup("https://example.com/completely-different-path")
    assert entry is not None
    assert entry.strategy == "header_tricks"


def test_clear_single_domain():
    record_success("https://a.com/p", "ua_cycling")
    record_success("https://b.com/p", "header_tricks")
    removed = clear("a.com")
    assert removed == 1
    assert lookup("https://a.com/p") is None
    assert lookup("https://b.com/p") is not None


def test_clear_all():
    record_success("https://a.com/p", "ua_cycling")
    record_success("https://b.com/p", "header_tricks")
    removed = clear()
    assert removed == 2
    assert lookup("https://a.com/p") is None
    assert lookup("https://b.com/p") is None


def test_clear_nonexistent_domain():
    assert clear("nonexistent.com") == 0


def test_list_entries_returns_sorted():
    record_success("https://b.com/p", "header_tricks")
    record_success("https://a.com/p", "ua_cycling")
    entries = list_entries()
    assert len(entries) == 2
    assert entries[0][0] == "a.com"
    assert entries[1][0] == "b.com"


def test_prune_removes_stale_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Entries with last_success older than 90 days are pruned on lookup."""
    cache_path = tmp_path / "bypass_cache.yaml"
    monkeypatch.setattr("archiveinator.bypass_cache.CACHE_PATH", cache_path)

    stale_date = "2020-01-01T00:00:00+00:00"
    data = {
        "stale.com": {
            "strategy": "ua_cycling",
            "last_success": stale_date,
            "attempts": 5,
            "successes": 3,
            "consecutive_failures": 0,
        },
        "fresh.com": {
            "strategy": "header_tricks",
            "last_success": datetime.now(tz=UTC).isoformat(),
            "attempts": 2,
            "successes": 2,
            "consecutive_failures": 0,
        },
    }
    with open(cache_path, "w") as f:
        yaml.dump(data, f)

    # stale.com should be pruned
    assert lookup("https://stale.com/page") is None
    # fresh.com should still be there
    assert lookup("https://fresh.com/page") is not None
