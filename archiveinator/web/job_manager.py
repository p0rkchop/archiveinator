"""In-memory job lifecycle manager with optional WebSocket progress streaming."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from archiveinator.config import data_dir as _data_dir


class JobManager:
    """Manages archive jobs in-process with async execution and progress streaming.

    Jobs are tracked in a dict keyed by job ID. Each job gets an asyncio task
    and an optional asyncio.Queue for WebSocket progress events.
    """

    def __init__(self) -> None:
        self._next_id = 1
        self._lock = asyncio.Lock()
        # job_id -> dict of job state (subset of what's in DB)
        self._in_flight: dict[int, dict[str, Any]] = {}
        # job_id -> asyncio.Queue for WebSocket progress
        self._queues: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        # job_id -> asyncio.Task for the running job
        self._tasks: dict[int, asyncio.Task[None]] = {}

    async def submit(
        self,
        user_id: int,
        url: str,
        profile_id: int | None = None,
    ) -> int:
        """Create and enqueue a new archive job. Returns the job ID."""
        async with self._lock:
            job_id = self._next_id
            self._next_id += 1
            now = time.time()

            self._in_flight[job_id] = {
                "id": job_id,
                "user_id": user_id,
                "url": url,
                "status": "pending",
                "profile_id": profile_id,
                "created_at": now,
            }
            self._queues[job_id] = asyncio.Queue()

        nq = self._queues[job_id]
        await nq.put({"type": "job_created", "job_id": job_id, "url": url})

        self._tasks[job_id] = asyncio.create_task(self._run_job(job_id))
        return job_id

    async def _run_job(self, job_id: int) -> None:
        """Background task: runs the archive pipeline."""
        from archiveinator.cli import _run_paywall_bypass
        from archiveinator.config import Config
        from archiveinator.pipeline import ArchiveContext, run_pipeline

        job = self._in_flight.get(job_id)
        if job is None:
            return

        q = self._queues.get(job_id)
        config = Config()
        user_output_dir = _data_dir() / "output" / str(job["user_id"])
        user_output_dir.mkdir(parents=True, exist_ok=True)

        ctx = ArchiveContext(url=job["url"], config=config)

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
        error: str | None = None

        try:
            # Run the pipeline
            ctx = await run_pipeline(ctx, config)

            # Paywall bypass if needed
            if ctx.paywalled:
                active = config.active_pipeline_steps()
                from typing import Any as _Any

                steps: list[dict[str, _Any]] = [{"step": s, "enabled": True} for s in active]
                ctx = await _run_paywall_bypass(ctx, steps)

            # Determine output path
            from archiveinator.naming import build_filename

            slug = (
                ctx.page_title or "untitled"
                if not ctx.is_partial
                else f"{ctx.page_title or 'untitled'}_partial"
            )
            fname = build_filename(job["url"], slug, partial=ctx.is_partial)
            output_path = user_output_dir / fname
            if ctx.page_html:
                output_path.write_text(ctx.page_html, encoding="utf-8")

            elapsed = round(time.time() - start, 1)
            job.update(
                status="completed",
                output_file=str(output_path.relative_to(_data_dir())),
                title=ctx.page_title,
                final_url=ctx.final_url,
                response_status=ctx.response_status,
                word_count=len(ctx.page_html.split()) if ctx.page_html else 0,
                paywalled=ctx.paywalled,
                paywall_reason=ctx.paywall_reason,
                bypass_method=ctx.bypass_method,
                bypass_cached=ctx.bypass_cached,
                is_partial=ctx.is_partial,
                duration_seconds=elapsed,
                step_log=ctx.step_log,
            )

            if q is not None:
                await q.put(
                    {
                        "type": "complete",
                        "job_id": job_id,
                        "title": ctx.page_title,
                        "output_file": job["output_file"],
                        "duration_seconds": elapsed,
                    }
                )

        except Exception as exc:
            elapsed = round(time.time() - start, 1)
            error = str(exc)
            job.update(status="failed", error=error, duration_seconds=elapsed)
            if q is not None:
                await q.put(
                    {
                        "type": "error",
                        "job_id": job_id,
                        "message": error,
                        "ts": elapsed,
                    }
                )

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


# Singleton
_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
