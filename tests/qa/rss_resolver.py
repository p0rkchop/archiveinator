"""RSS/Atom feed resolver for QA site catalog.

When a site entry includes an ``rss_feed`` URL, this module fetches the feed
and returns the latest article URL.  A session-level in-memory cache prevents
redundant network requests when multiple tests parametrise the same site.
"""

from __future__ import annotations

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import Optional

# Session cache: rss_feed_url -> resolved article url
_CACHE: dict[str, str | None] = {}

_TIMEOUT = 10  # seconds

_ATOM_NS = "http://www.w3.org/2005/Atom"


def resolve_article_url(rss_url: str) -> str | None:
    """Fetch *rss_url* and return the URL of the most recent article.

    Returns None if the feed cannot be fetched or parsed.
    Results are cached in-process for the lifetime of the test session.
    """
    if rss_url in _CACHE:
        return _CACHE[rss_url]

    url = _fetch_and_parse(rss_url)
    _CACHE[rss_url] = url
    return url


def _fetch_and_parse(rss_url: str) -> str | None:
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

    # RSS 2.0: <rss><channel><item><link>
    # Try RSS first
    channel = root.find("channel")
    if channel is not None:
        item = channel.find("item")
        if item is not None:
            link = item.findtext("link")
            if link and link.startswith("http"):
                return link.strip()

    # Atom: <feed><entry><link href="...">
    # Atom uses namespaces
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    if entry is not None:
        link_el = entry.find(f"{{{_ATOM_NS}}}link")
        if link_el is not None:
            href = link_el.get("href", "")
            if href.startswith("http"):
                return href.strip()

    # RSS without namespace, or alternate element names
    for item_tag in ("item", "entry"):
        item = root.find(f".//{item_tag}")
        if item is not None:
            for link_tag in ("link", "url"):
                link = item.findtext(link_tag)
                if link and link.startswith("http"):
                    return link.strip()
            # Atom-style link element (no namespace match above)
            link_el = item.find("link")
            if link_el is not None:
                href = link_el.get("href", "")
                if href.startswith("http"):
                    return href.strip()

    return None


def resolve_site_url(site_spec: dict) -> str:
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
    return site_spec["url"]
