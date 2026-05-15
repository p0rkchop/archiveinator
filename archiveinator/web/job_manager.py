"""In-memory job lifecycle manager with optional WebSocket progress streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

from archiveinator.config import data_dir as _data_dir
from archiveinator.web.db import get_session_factory

logger = logging.getLogger(__name__)


class JobManager:
    """Manages archive jobs in-process with async execution and progress streaming.

    Jobs are tracked in a dict keyed by job ID. Each job gets an asyncio task
    and an optional asyncio.Queue for WebSocket progress events.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # job_id -> dict of job state (keyed by DB job ID)
        self._in_flight: dict[int, dict[str, Any]] = {}
        # job_id -> asyncio.Queue for WebSocket progress
        self._queues: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        # job_id -> asyncio.Task for the running job
        self._tasks: dict[int, asyncio.Task[None]] = {}

    async def submit(
        self,
        db_job_id: int,
        user_id: int,
        url: str,
        profile_id: int | None = None,
        disabled_steps: set[str] | None = None,
    ) -> None:
        """Enqueue an archive job using the DB job ID as the key."""
        async with self._lock:
            now = time.time()
            self._in_flight[db_job_id] = {
                "id": db_job_id,
                "user_id": user_id,
                "url": url,
                "status": "pending",
                "profile_id": profile_id,
                "disabled_steps": disabled_steps or set(),
                "created_at": now,
            }
            self._queues[db_job_id] = asyncio.Queue()

        nq = self._queues[db_job_id]
        await nq.put({"type": "job_created", "job_id": db_job_id, "url": url})

        self._tasks[db_job_id] = asyncio.create_task(self._run_job(db_job_id))

    async def _run_job(self, job_id: int) -> None:
        """Background task: runs the archive pipeline.

        The DB record is created by the POST /archive route before
        submitting to the job manager. This method updates it on completion.
        """
        from archiveinator.cli import _run_paywall_bypass
        from archiveinator.config import Config
        from archiveinator.pipeline import ArchiveContext

        job = self._in_flight.get(job_id)
        if job is None:
            return

        q = self._queues.get(job_id)
        config = Config()
        user_output_dir = _data_dir() / "output" / str(job["user_id"])
        user_output_dir.mkdir(parents=True, exist_ok=True)

        ctx = ArchiveContext(url=job["url"], config=config)
        ctx.disabled_steps = job.get("disabled_steps", set())

        # Hook ctx.log to also push to WebSocket
        original_log = ctx.log

        def _hooked_log(step: str, msg: str) -> None:
            original_log(step, msg)
            if q is not None:
                q.put_nowait(
                    {
                        "type": "step",
                        "step": step,
                        "message": msg,
                        "ts": round(time.time() - job["created_at"], 1),
                    }
                )

        ctx.log = _hooked_log  # type: ignore[method-assign]

        job["status"] = "running"
        if q is not None:
            await q.put(
                {
                    "type": "step",
                    "step": "pipeline",
                    "message": "Starting archive pipeline",
                    "ts": 0,
                }
            )

        start = time.time()

        try:
            # --- Page load with retries ---
            from archiveinator.steps.page_load import PageLoadError
            from archiveinator.steps.page_load import run as page_load_run

            last_page_error: PageLoadError | None = None
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    await page_load_run(ctx)
                    last_page_error = None
                    break
                except PageLoadError as e:
                    last_page_error = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)

            # Handle page load failure gracefully
            if last_page_error is not None:
                import html as html_mod

                error_str = str(last_page_error)
                ctx.page_html = (
                    "<!DOCTYPE html>\n<html><head><title>"
                    "Archive Error: " + ctx.url + '</title><meta charset="utf-8"></head>\n<body>'
                    "<h1>Archive Error</h1>"
                    '<p>Failed to load: <a href="' + ctx.url + '">' + ctx.url + "</a></p>"
                    "<p>Error: " + html_mod.escape(error_str[:500]) + "</p></body></html>"
                )
                ctx.page_title = f"Archive Error: {ctx.url}"
                ctx.final_url = ctx.url
                ctx.is_partial = True
                ctx.paywalled = False

            # --- Paywall bypass suite ---
            if ctx.paywalled:
                active = config.active_pipeline_steps()
                _run_paywall_bypass(ctx, active)
                if ctx.paywalled:
                    ctx.is_partial = True

            # --- Image deduplication ---
            active_steps = config.active_pipeline_steps()
            if "image_dedup" in active_steps:
                from archiveinator.steps.image_dedup import run as image_dedup_run

                await image_dedup_run(ctx)

            # --- Asset inlining ---
            if "asset_inlining" in active_steps:
                from archiveinator.steps.asset_inlining import AssetInliningError
                from archiveinator.steps.asset_inlining import run as inline_run

                try:
                    await inline_run(ctx)
                except AssetInliningError:
                    ctx.is_partial = True

            # --- Determine output filename ---
            from archiveinator.naming import build_filename

            ts_dt = datetime.fromtimestamp(start)
            fname = build_filename(
                job["url"],
                ctx.page_title or "untitled",
                ts=ts_dt,
                partial=ctx.is_partial,
            )
            output_path = user_output_dir / fname
            if ctx.page_html:
                output_path.write_text(ctx.page_html, encoding="utf-8")

            word_count_val = len(ctx.page_html.split()) if ctx.page_html else 0
            elapsed = round(time.time() - start, 1)
            rel_path = str(output_path.relative_to(_data_dir())) if ctx.page_html else None

            job.update(
                status="completed",
                output_file=rel_path,
                title=ctx.page_title,
                final_url=ctx.final_url,
                response_status=ctx.response_status,
                word_count=word_count_val,
                paywalled=ctx.paywalled,
                paywall_reason=ctx.paywall_reason,
                bypass_method=ctx.bypass_method,
                bypass_cached=ctx.bypass_cached,
                is_partial=ctx.is_partial,
                duration_seconds=elapsed,
                step_log=ctx.step_log,
            )

            # Update DB
            self._update_db(
                job_id,
                {
                    "status": "completed",
                    "output_file": rel_path,
                    "title": ctx.page_title,
                    "final_url": ctx.final_url,
                    "response_status": ctx.response_status,
                    "word_count": word_count_val,
                    "paywalled": ctx.paywalled,
                    "paywall_reason": ctx.paywall_reason,
                    "bypass_method": ctx.bypass_method,
                    "bypass_cached": ctx.bypass_cached,
                    "is_partial": ctx.is_partial,
                    "step_log_json": json.dumps(ctx.step_log),
                    "duration_seconds": elapsed,
                    "completed_at": datetime.now(),
                },
            )

            if q is not None:
                await q.put(
                    {
                        "type": "complete",
                        "job_id": job_id,
                        "title": ctx.page_title,
                        "output_file": rel_path,
                        "duration_seconds": elapsed,
                    }
                )

            # Send email notification
            await self._send_email_notification(job_id, "completed")

        except Exception as exc:
            elapsed = round(time.time() - start, 1)
            error = str(exc)
            job.update(status="failed", error=error, duration_seconds=elapsed)
            self._update_db(
                job_id,
                {
                    "status": "failed",
                    "error": error,
                    "duration_seconds": elapsed,
                    "completed_at": datetime.now(),
                },
            )
            if q is not None:
                await q.put(
                    {
                        "type": "error",
                        "job_id": job_id,
                        "message": error,
                        "ts": elapsed,
                    }
                )

            # Send email notification
            await self._send_email_notification(job_id, "failed")

    def _update_db(self, job_id: int, updates: dict[str, Any]) -> None:
        """Update the DB record for a job."""
        from archiveinator.web.models import ArchiveJob

        session_factory = get_session_factory()
        session = session_factory()
        try:
            job = session.query(ArchiveJob).filter(ArchiveJob.id == job_id).first()
            if job is not None:
                for key, value in updates.items():
                    setattr(job, key, value)
                session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to update DB for job %d", job_id)
        finally:
            session.close()

    def get(self, job_id: int) -> dict[str, Any] | None:
        """Get job state from in-memory store."""
        return self._in_flight.get(job_id)

    def list_by_user(self, user_id: int, page: int = 1, per_page: int = 20) -> list[dict[str, Any]]:
        """List jobs for a user, newest first, from in-memory store.

        This only returns in-flight jobs. Full history is in the DB.
        """
        jobs = [j for j in self._in_flight.values() if j["user_id"] == user_id]
        jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
        offset = (page - 1) * per_page
        return jobs[offset : offset + per_page]

    async def get_queue(self, job_id: int) -> asyncio.Queue[dict[str, Any]] | None:
        """Get the progress queue for a job. Returns None if job doesn't exist."""
        return self._queues.get(job_id)

    def update(self, job_id: int, **kwargs: Any) -> None:
        """Update in-memory job state."""
        if job_id in self._in_flight:
            self._in_flight[job_id].update(kwargs)

    async def _send_email_notification(self, job_id: int, status: str) -> None:
        """Send email notification for job completion or failure if user opted in."""
        from archiveinator.web.emailer import notify_job_complete, notify_job_failed
        from archiveinator.web.models import ArchiveJob as ArchiveJobModel
        from archiveinator.web.models import User as UserModel

        session_factory = get_session_factory()
        session = session_factory()
        try:
            job = session.query(ArchiveJobModel).filter(ArchiveJobModel.id == job_id).first()
            if job is None:
                return
            user = session.query(UserModel).filter(UserModel.id == job.user_id).first()
            if user is None or not user.email:
                return

            # Check if user has email notifications enabled
            from archiveinator.web.models import UserConfig

            config = session.query(UserConfig).filter(UserConfig.user_id == user.id).first()
            if config is None or not config.email_notifications_enabled:
                return

            if status == "completed":
                notify_job_complete(user.email, job)
            elif status == "failed":
                notify_job_failed(user.email, job)
        except Exception:
            logger.exception("Failed to send email notification for job %d", job_id)
        finally:
            session.close()


# Singleton
_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
