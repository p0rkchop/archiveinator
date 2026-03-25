"""RSS/Atom feed resolver for QA site catalog.

When a site entry includes an ``rss_feed`` URL, this module fetches the feed
and returns article URLs.  A session-level in-memory cache prevents
redundant network requests when multiple tests parametrise the same site.

Delegates to :func:`check_feeds.check_one` for fetch + parse with hard timeouts.
"""

from __future__ import annotations

from tests.qa.check_feeds import check_one

# Session cache: rss_feed_url -> list of article urls
_CACHE: dict[str, list[str]] = {}


def resolve_article_urls(rss_url: str) -> list[str]:
    """Fetch *rss_url* and return up to 5 recent article URLs.

    Returns empty list if the feed cannot be fetched or parsed.
    Results are cached in-process for the lifetime of the test session.
    """
    if rss_url in _CACHE:
        return _CACHE[rss_url]

    result = check_one(rss_url)
    urls = result.article_urls or ([result.article_url] if result.article_url else [])
    _CACHE[rss_url] = urls
    return urls


def resolve_article_url(rss_url: str) -> str | None:
    """Fetch *rss_url* and return the URL of the most recent article.

    Returns None if the feed cannot be fetched or parsed.
    """
    urls = resolve_article_urls(rss_url)
    return urls[0] if urls else None


def resolve_site_url(site_spec: dict, index: int = 0) -> str:
    """Return the URL to use for testing *site_spec*.

    If the spec has an ``rss_feed`` key, fetches the feed and uses the
    article at *index* (default: latest).  Falls back to the stored ``url``
    if the feed cannot be resolved.
    """
    rss_feed = site_spec.get("rss_feed")
    if rss_feed:
        urls = resolve_article_urls(rss_feed)
        if urls and index < len(urls):
            return urls[index]
        if urls:
            return urls[0]
    return site_spec["url"]
