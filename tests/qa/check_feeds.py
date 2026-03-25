#!/usr/bin/env python3
"""CLI tool to check RSS feed health for sites in sites.yaml.

Fetches feed bytes with a hard socket-level timeout, then parses with
feedparser.  Never hangs.

Usage:
    uv run tests/qa/check_feeds.py url https://slate.com/feeds/all.rss
    uv run tests/qa/check_feeds.py site "Slate"
    uv run tests/qa/check_feeds.py all
    uv run tests/qa/check_feeds.py all --failures-only
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import feedparser
import yaml

SITE_TIMEOUT = 12  # seconds per feed fetch
LOG_PATH = Path(__file__).parent / "check_feeds.log"
SITES_PATH = Path(__file__).parent / "sites.yaml"

_io_lock = threading.Lock()


@dataclass
class FeedResult:
    name: str
    rss_url: str
    status: str  # ok | http_error | no_entries | parse_error | timeout | fetch_error
    detail: str | None = None
    article_url: str | None = None
    article_urls: list[str] | None = None


def check_one(rss_url: str, timeout: int = SITE_TIMEOUT, name: str = "") -> FeedResult:
    """Check a single RSS feed URL.  Never hangs beyond *timeout* seconds.

    Fetches raw bytes with urllib (hard timeout), then parses with feedparser.
    """
    # Step 1: fetch bytes ourselves so we control the timeout
    try:
        req = urllib.request.Request(
            rss_url,
            headers={"User-Agent": "archiveinator-qa/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            raw = resp.read()
    except urllib.error.HTTPError as e:
        return FeedResult(name=name, rss_url=rss_url, status="http_error", detail=f"HTTP {e.code}")
    except urllib.error.URLError as e:
        return FeedResult(
            name=name, rss_url=rss_url, status="fetch_error", detail=str(e.reason)[:100]
        )
    except TimeoutError:
        return FeedResult(
            name=name, rss_url=rss_url, status="timeout", detail=f"no response in {timeout}s"
        )
    except OSError as e:
        return FeedResult(name=name, rss_url=rss_url, status="fetch_error", detail=str(e)[:100])

    if status_code and status_code >= 400:
        return FeedResult(
            name=name, rss_url=rss_url, status="http_error", detail=f"HTTP {status_code}"
        )

    # Step 2: parse the already-fetched bytes (no network, instant)
    d = feedparser.parse(raw)

    if d.get("bozo") and not d.get("entries"):
        exc = d.get("bozo_exception")
        detail = str(exc)[:100] if exc else "malformed feed"
        return FeedResult(name=name, rss_url=rss_url, status="parse_error", detail=detail)

    entries = d.get("entries", [])
    if not entries:
        return FeedResult(
            name=name, rss_url=rss_url, status="no_entries", detail="feed parsed but no entries"
        )

    links = []
    for entry in entries:
        link = entry.get("link", "")
        if link and link.startswith("http"):
            links.append(link.strip())

    if links:
        return FeedResult(
            name=name,
            rss_url=rss_url,
            status="ok",
            article_url=links[0],
            detail=links[0],
            article_urls=links[:5],
        )

    return FeedResult(
        name=name, rss_url=rss_url, status="no_entries", detail="entries present but no link"
    )


def _format_result(r: FeedResult) -> str:
    label = r.name or r.rss_url[:50]
    if r.status == "ok":
        return f"  OK    {label:40} {r.article_url}"
    if r.status == "skip":
        return f"  SKIP  {label}"
    return f"  FAIL  {label:40} [{r.status}] {r.detail}"


def _print(line: str) -> None:
    with _io_lock:
        print(line, flush=True)


def _load_sites() -> list[dict]:
    with open(SITES_PATH) as f:
        return yaml.safe_load(f)["sites"]


# ── CLI subcommands ──────────────────────────────────────────────


def cmd_url(args: argparse.Namespace) -> None:
    r = check_one(args.rss_url, timeout=args.timeout, name="(url)")
    print(_format_result(r))
    if r.status != "ok":
        sys.exit(1)


def cmd_site(args: argparse.Namespace) -> None:
    sites = _load_sites()
    matches = [s for s in sites if s["name"] == args.name]
    if not matches:
        print(f"No site named {args.name!r}")
        sys.exit(1)
    site = matches[0]
    rss = site.get("rss_feed")
    if not rss:
        print(f"  SKIP  {site['name']:40} (no rss_feed)")
        sys.exit(0)
    r = check_one(rss, timeout=args.timeout, name=site["name"])
    print(_format_result(r))
    if r.status != "ok":
        sys.exit(1)


def cmd_all(args: argparse.Namespace) -> None:
    sites = _load_sites()

    to_check: list[tuple[str, str]] = []
    skip_count = 0

    for site in sites:
        rss = site.get("rss_feed")
        if rss:
            to_check.append((site["name"], rss))
        else:
            skip_count += 1
            if not args.failures_only:
                _print(f"  SKIP  {site['name']}")

    print(f"Checking {len(to_check)} feeds ({skip_count} skipped) — log: {args.log}", flush=True)

    ok_count = 0
    fail_count = 0

    with open(args.log, "w") as log_file:
        log_file.write(
            json.dumps(
                {"event": "run_start", "ts": datetime.now(UTC).isoformat(), "total": len(to_check)}
            )
            + "\n"
        )
        log_file.flush()

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(check_one, rss, args.timeout, name): name for name, rss in to_check
            }
            for future in as_completed(futures):
                r = future.result()  # check_one never raises
                record = asdict(r)
                log_file.write(json.dumps(record) + "\n")
                log_file.flush()

                if r.status == "ok":
                    ok_count += 1
                    if not args.failures_only:
                        _print(_format_result(r))
                else:
                    fail_count += 1
                    _print(_format_result(r))

        log_file.write(
            json.dumps({"event": "run_end", "ok": ok_count, "fail": fail_count, "skip": skip_count})
            + "\n"
        )

    print(f"\nOK: {ok_count}  FAIL: {fail_count}  SKIP: {skip_count}")
    if fail_count:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check RSS feeds")
    parser.add_argument(
        "--timeout", type=int, default=SITE_TIMEOUT, help="Per-feed timeout in seconds"
    )
    sub = parser.add_subparsers(dest="command")

    p_url = sub.add_parser("url", help="Check a single RSS URL")
    p_url.add_argument("rss_url", help="RSS/Atom feed URL to check")

    p_site = sub.add_parser("site", help="Check a site by name from sites.yaml")
    p_site.add_argument("name", help="Site name (exact match)")

    p_all = sub.add_parser("all", help="Check all feeds in sites.yaml")
    p_all.add_argument("--failures-only", action="store_true")
    p_all.add_argument("--workers", type=int, default=16)
    p_all.add_argument("--log", type=Path, default=LOG_PATH)

    args = parser.parse_args()
    if args.command == "url":
        cmd_url(args)
    elif args.command == "site":
        cmd_site(args)
    elif args.command == "all":
        cmd_all(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
