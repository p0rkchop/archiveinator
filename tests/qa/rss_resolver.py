"""RSS/Atom feed resolver for QA site catalog.

When a site entry includes an ``rss_feed`` URL, this module fetches the feed
and returns the latest article URL.  A session-level in-memory cache prevents
redundant network requests when multiple tests parametrise the same site.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

# Session cache: rss_feed_url -> list of article URLs (or None if feed failed)
_CACHE: dict[str, list[str] | None] = {}

_TIMEOUT = 10  # seconds

_ATOM_NS = "http://www.w3.org/2005/Atom"


def resolve_article_url(rss_url: str) -> str | None:
    """Fetch *rss_url* and return the URL of the most recent article.

    Returns None if the feed cannot be fetched or parsed.
    Results are cached in-process for the lifetime of the test session.
    """
    if rss_url not in _CACHE:
        _CACHE[rss_url] = _fetch_and_parse_all(rss_url)
    cached = _CACHE[rss_url]
    return cached[0] if cached else None


def _fetch_and_parse_all(rss_url: str) -> list[str] | None:
    """Fetch RSS/Atom feed and return list of article URLs (most recent first)."""
    try:
        req = urllib.request.Request(
            rss_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; archiveinator-qa/1.0; +https://github.com)"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = resp.read()
    except (urllib.error.URLError, OSError):
        return None

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None

    urls: list[str] = []

    # RSS 2.0: <rss><channel><item><link>
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            link = item.findtext("link")
            if link and link.startswith("http"):
                urls.append(link.strip())

    # Atom: <feed><entry><link href="...">
    # Atom uses namespaces
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        link_el = entry.find(f"{{{_ATOM_NS}}}link")
        if link_el is not None:
            href = link_el.get("href", "")
            if href.startswith("http"):
                urls.append(href.strip())
        # Fallback: look for <link> without namespace
        else:
            link_el = entry.find("link")
            if link_el is not None:
                href = link_el.get("href", "")
                if href.startswith("http"):
                    urls.append(href.strip())

    # RSS without namespace, or alternate element names
    if not urls:
        for item_tag in ("item", "entry"):
            for item in root.findall(f".//{item_tag}"):
                for link_tag in ("link", "url"):
                    link = item.findtext(link_tag)
                    if link and link.startswith("http"):
                        urls.append(link.strip())
                # Atom-style link element (no namespace match above)
                link_el = item.find("link")
                if link_el is not None:
                    href = link_el.get("href", "")
                    if href.startswith("http"):
                        urls.append(href.strip())

    # Deduplicate while preserving order (most recent first)
    seen = set()
    deduped = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped if deduped else None


def resolve_article_urls(rss_url: str, max_articles: int = 5) -> list[str]:
    """Fetch *rss_url* and return up to *max_articles* most recent article URLs.

    Returns empty list if the feed cannot be fetched or parsed.
    Results are cached in-process for the lifetime of the test session.
    """
    if rss_url not in _CACHE:
        _CACHE[rss_url] = _fetch_and_parse_all(rss_url)
    cached = _CACHE[rss_url]
    if not cached:
        return []
    return cached[:max_articles]


def resolve_site_url(site_spec: dict[str, Any]) -> str:
    """Return the URL to use for testing *site_spec*.

    If the spec has an ``rss_feed`` key, fetches the feed and uses the
    latest article URL.  Falls back to the stored ``url`` if the feed
    cannot be resolved.
    """
    rss_feed = site_spec.get("rss_feed")
    if rss_feed:
        resolved = resolve_article_url(rss_feed)
        if resolved:
            return resolved
    url: str = site_spec["url"]
    return url
