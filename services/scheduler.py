#!/usr/bin/env python3
"""
Task scheduler service

Manages periodic tasks (backups, log cleanup, auto-close tickets, etc.)
Runs scheduled jobs at specified intervals.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing periodic tasks."""

    def __init__(self) -> None:
        self.tasks: list[asyncio.Task] = []
        self.running: bool = False
        # {job_id: {'func': callable, 'interval': seconds, 'last_run': datetime|None, 'next_run': datetime}}
        self.jobs: dict[str, dict] = {}

    async def add_job(
        self,
        job_id: str,
        func: Callable[[], Awaitable[None]],
        interval_seconds: int,
        run_immediately: bool = True,
    ) -> None:
        """
        Add periodic job to scheduler.

        Args:
            job_id: Unique job identifier.
            func: Async callable to execute (no-arg coroutine).
            interval_seconds: Interval between executions in seconds.
            run_immediately: If True, run job immediately on first iteration,
                             else wait for interval before first execution.
        """
        if job_id in self.jobs:
            logger.warning("Job %s is already registered, overwriting", job_id)

        next_run = datetime.now() if run_immediately else datetime.now() + timedelta(
            seconds=interval_seconds
        )

        self.jobs[job_id] = {
            "func": func,
            "interval": interval_seconds,
            "last_run": None,
            "next_run": next_run,
        }
        logger.info(
            "Added job: %s (interval: %ss, immediate: %s)",
            job_id,
            interval_seconds,
            run_immediately,
        )

    async def remove_job(self, job_id: str) -> None:
        """
        Remove job from scheduler.

        Args:
            job_id: Job identifier to remove.
        """
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info("Removed job: %s", job_id)
        else:
            logger.warning("Attempted to remove non-existing job: %s", job_id)

    async def start(self) -> None:
        """Start scheduler and run all jobs."""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        logger.info("Scheduler service started")

        task = asyncio.create_task(self._run_scheduler(), name="scheduler_loop")
        self.tasks.append(task)

    async def _run_scheduler(self) -> None:
        """Main scheduler loop - execute jobs on schedule."""
        try:
            while self.running:
                now = datetime.now()

                # Итерируемся по копии, чтобы избежать ошибок при изменении self.jobs во время обхода
                for job_id, job_info in list(self.jobs.items()):
                    next_run = job_info.get("next_run")
                    if next_run is None:
                        # На всякий случай инициализируем
                        job_info["next_run"] = now + timedelta(
                            seconds=job_info["interval"]
                        )
                        continue

                    if now >= next_run:
                        try:
                            logger.debug("Executing job: %s", job_id)
                            await job_info["func"]()

                            job_info["last_run"] = now
                            job_info["next_run"] = now + timedelta(
                                seconds=job_info["interval"]
                            )
                            logger.debug("Job %s completed", job_id)
                        except Exception as e:
                            logger.error(
                                "Job %s failed: %s", job_id, e, exc_info=True
                            )
                            # Reschedule anyway to avoid getting stuck
                            job_info["next_run"] = now + timedelta(
                                seconds=job_info["interval"]
                            )

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
        except Exception as e:
            logger.error("Scheduler error: %s", e, exc_info=True)

    async def stop(self) -> None:
        """Stop scheduler and cancel all tasks."""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping scheduler... (tasks: %d)", len(self.tasks))

        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.tasks.clear()
        logger.info("Scheduler service stopped")

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """
        Get status of scheduled job.

        Args:
            job_id: Job identifier.

        Returns:
            Job status dict or None if not found.
        """
        job = self.jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job_id,
            "interval": job["interval"],
            "last_run": job["last_run"],
            "next_run": job["next_run"],
        }

    def get_all_jobs(self) -> dict:
        """
        Get all scheduled jobs status.

        Returns:
            Dictionary of all jobs with their status.
        """
        return {
            job_id: {
                "interval": job["interval"],
                "last_run": job["last_run"],
                "next_run": job["next_run"],
            }
            for job_id, job in self.jobs.items()
        }


# Global instance
scheduler_service = SchedulerService()
