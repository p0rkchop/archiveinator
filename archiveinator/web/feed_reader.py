"""Feed reader: RSS/Atom feed polling, parsing, and auto-archiving."""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timezone

import feedparser

from archiveinator.web.job_manager import get_job_manager

logger = logging.getLogger(__name__)


def check_feed(feed_id: int) -> int:
    """Fetch and process a single RSS feed.

    Returns the number of new items discovered.
    """
    from archiveinator.web.db import get_session_factory
    from archiveinator.web.models import ArchiveJob, FeedItem, RssFeed

    session_factory = get_session_factory()
    session = session_factory()
    try:
        feed = session.query(RssFeed).filter(RssFeed.id == feed_id).first()
        if feed is None:
            logger.warning("Feed %d not found", feed_id)
            return 0

        parsed = feedparser.parse(feed.feed_url)
        if parsed.bozo and not parsed.entries:
            logger.warning("Feed %d parse error: %s", feed_id, parsed.bozo_exception)
            return 0

        if parsed.get("etag"):
            feed.last_etag = parsed.etag
        if parsed.get("modified"):
            feed.last_modified = parsed.modified

        new_count = 0
        for entry in parsed.entries:
            url = entry.get("link", "").strip()
            if not url:
                continue

            existing = (
                session.query(FeedItem)
                .filter(FeedItem.feed_id == feed_id, FeedItem.url == url)
                .first()
            )
            if existing is not None:
                continue

            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)  # type: ignore[misc]  # noqa: UP017
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)  # type: ignore[misc]  # noqa: UP017

            item = FeedItem(
                feed_id=feed_id,
                url=url,
                title=entry.get("title", ""),
                published_at=published,
            )
            session.add(item)
            session.flush()

            job = ArchiveJob(
                user_id=feed.user_id,
                url=url,
                status="pending",
                site_profile_id=feed.site_profile_id,
                site_profile_label=feed.label,
            )
            session.add(job)
            session.flush()

            item.archived = True
            item.job_id = job.id

            jm = get_job_manager()
            asyncio.create_task(jm.submit(job.id, feed.user_id, url, profile_id=feed.site_profile_id))

            new_count += 1

        feed.last_checked_at = datetime.utcnow()
        session.commit()

        if new_count:
            logger.info("Feed %d: %d new items archived", feed_id, new_count)
        return new_count

    except Exception:
        session.rollback()
        logger.exception("Failed to check feed %d", feed_id)
        return 0
    finally:
        session.close()


def check_all_feeds() -> None:
    """Check all feeds whose interval has elapsed."""
    from archiveinator.web.db import get_session_factory
    from archiveinator.web.models import RssFeed

    session_factory = get_session_factory()
    session = session_factory()
    try:
        feeds = session.query(RssFeed).all()
        now = datetime.utcnow()
        for feed in feeds:
            if feed.last_checked_at is not None:
                elapsed = (now - feed.last_checked_at).total_seconds()
                if elapsed < feed.check_interval_minutes * 60:
                    continue

            asyncio.create_task(_check_feed_async(feed.id))

        logger.debug("Scheduled check of %d feeds", len(feeds))
    except Exception:
        logger.exception("Failed to enumerate feeds")
    finally:
        session.close()


async def _check_feed_async(feed_id: int) -> None:
    """Run check_feed in a thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, functools.partial(check_feed, feed_id))
