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

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing periodic tasks"""

    def __init__(self):
        self.tasks = []
        self.running = False
        self.jobs = {}  # Store scheduled jobs: {job_id: {'func': callable, 'interval': seconds}}

    async def add_job(
        self,
        job_id: str,
        func: Callable,
        interval_seconds: int,
        run_immediately: bool = True
    ):
        """
        Add periodic job to scheduler

        Args:
            job_id: Unique job identifier
            func: Async callable to execute
            interval_seconds: Interval between executions in seconds
            run_immediately: If True, run job immediately on first iteration, 
                           else wait for interval before first execution
        """
        # Calculate next run time
        if run_immediately:
            next_run = datetime.now()
        else:
            next_run = datetime.now() + timedelta(seconds=interval_seconds)

        self.jobs[job_id] = {
            'func': func,
            'interval': interval_seconds,
            'last_run': None,
            'next_run': next_run
        }
        logger.info(f"Added job: {job_id} (interval: {interval_seconds}s, immediate: {run_immediately})")

    async def remove_job(self, job_id: str):
        """
        Remove job from scheduler

        Args:
            job_id: Job identifier to remove
        """
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Removed job: {job_id}")

    async def start(self):
        """Start scheduler and run all jobs"""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        logger.info("Scheduler service started")

        # Create background task for job execution
        task = asyncio.create_task(self._run_scheduler())
        self.tasks.append(task)

    async def _run_scheduler(self):
        """Main scheduler loop - execute jobs on schedule"""
        try:
            while self.running:
                now = datetime.now()

                for job_id, job_info in self.jobs.items():
                    # Check if it's time to run this job
                    if now >= job_info['next_run']:
                        try:
                            logger.debug(f"Executing job: {job_id}")
                            await job_info['func']()

                            # Update timing
                            job_info['last_run'] = now
                            job_info['next_run'] = now + timedelta(
                                seconds=job_info['interval']
                            )
                            logger.debug(f"Job {job_id} completed")
                        except Exception as e:
                            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
                            # Reschedule anyway to avoid getting stuck
                            job_info['next_run'] = now + timedelta(
                                seconds=job_info['interval']
                            )

                # Sleep briefly to prevent CPU spinning
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)

    async def stop(self):
        """Stop scheduler and cancel all tasks"""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping scheduler...")

        # Cancel all tasks
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
        Get status of scheduled job

        Args:
            job_id: Job identifier

        Returns:
            Job status dict or None if not found
        """
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        return {
            'job_id': job_id,
            'interval': job['interval'],
            'last_run': job['last_run'],
            'next_run': job['next_run']
        }

    def get_all_jobs(self) -> dict:
        """
        Get all scheduled jobs status

        Returns:
            Dictionary of all jobs with their status
        """
        return {
            job_id: {
                'interval': job['interval'],
                'last_run': job['last_run'],
                'next_run': job['next_run']
            }
            for job_id, job in self.jobs.items()
        }


# Global instance
scheduler_service = SchedulerService()
