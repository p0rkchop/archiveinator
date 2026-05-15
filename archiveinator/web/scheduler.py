"""APScheduler integration: cron-based archiving and schedule management."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from archiveinator.web.job_manager import get_job_manager

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the shared scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the APScheduler if not already running."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("APScheduler started")


def shutdown_scheduler() -> None:
    """Shut down the scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler shut down")


def add_archive_schedule(
    schedule_id: int,
    user_id: int,
    url: str,
    cron_expression: str,
    profile_id: int | None = None,
) -> None:
    """Add a cron job to the scheduler for archiving a URL."""
    sched = get_scheduler()

    # Parse cron expression (5-field: minute hour day month day_of_week)
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        logger.warning("Invalid cron expression for schedule %d: %s", schedule_id, cron_expression)
        return

    sched.add_job(
        _run_scheduled_archive,
        trigger="cron",
        id=str(schedule_id),
        args=[user_id, url, profile_id, schedule_id],
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Added schedule %d: cron='%s' url=%s", schedule_id, cron_expression, url)


def remove_archive_schedule(schedule_id: int) -> None:
    """Remove a cron job from the scheduler."""
    sched = get_scheduler()
    try:
        sched.remove_job(str(schedule_id))
        logger.info("Removed schedule %d", schedule_id)
    except Exception:
        pass  # Job may not exist


def restore_schedules() -> None:
    """Restore all enabled schedules from the database on server startup."""
    from archiveinator.web.db import get_session_factory
    from archiveinator.web.models import ScheduledTask

    session_factory = get_session_factory()
    session = session_factory()
    try:
        schedules = session.query(ScheduledTask).filter(ScheduledTask.enabled.is_(True)).all()
        for s in schedules:
            add_archive_schedule(
                schedule_id=s.id,
                user_id=s.user_id,
                url=s.url,
                cron_expression=s.cron_expression,
                profile_id=s.site_profile_id,
            )
        if schedules:
            logger.info("Restored %d schedules", len(schedules))
    except Exception:
        logger.exception("Failed to restore schedules")
    finally:
        session.close()


async def _run_scheduled_archive(
    user_id: int,
    url: str,
    profile_id: int | None,
    schedule_id: int,
) -> None:
    """Execute a scheduled archive job.

    Called by APScheduler when a cron trigger fires.
    """
    from archiveinator.web.db import get_session_factory
    from archiveinator.web.models import ArchiveJob, ScheduledTask

    jm = get_job_manager()

    # Create DB record
    session_factory = get_session_factory()
    session = session_factory()
    try:
        job = ArchiveJob(
            user_id=user_id,
            url=url,
            status="pending",
            site_profile_id=profile_id,
        )
        session.add(job)
        session.flush()
        job_id = job.id

        # Update last_run_at on the schedule
        from datetime import datetime

        (
            session.query(ScheduledTask)
            .filter(ScheduledTask.id == schedule_id)
            .update({"last_run_at": datetime.utcnow(), "last_job_id": job_id})
        )
        session.commit()

        # Submit to job manager using the DB job ID as the key
        await jm.submit(job_id, user_id, url, profile_id=profile_id)
    except Exception:
        session.rollback()
        logger.exception("Failed to create scheduled archive job")
    finally:
        session.close()
