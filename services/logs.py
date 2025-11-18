#!/usr/bin/env python3
"""
Log cleanup service

Manages log file retention and automatic cleanup of old logs.
Prevents disk space issues by removing logs older than retention period.
"""

import os
import logging
from datetime import datetime, timedelta

from config import DATA_DIR, LOG_CLEANUP_ENABLED, LOG_RETENTION_DAYS, TIMEZONE

logger = logging.getLogger(__name__)


class LogService:
    """Service for managing log file lifecycle."""

    def cleanup_old_logs(self) -> None:
        """
        Remove old log files if cleanup is enabled.

        Deletes log files older than LOG_RETENTION_DAYS.
        Only runs if LOG_CLEANUP_ENABLED is True in config.
        """
        if not LOG_CLEANUP_ENABLED:
            logger.debug("Log cleanup disabled in config")
            return

        if LOG_RETENTION_DAYS <= 0:
            logger.warning(
                "Log cleanup enabled but LOG_RETENTION_DAYS=%s is not positive, skipping",
                LOG_RETENTION_DAYS,
            )
            return

        try:
            # Calculate cutoff date (anything older than this will be deleted)
            cutoff = datetime.now(TIMEZONE) - timedelta(days=LOG_RETENTION_DAYS)
            log_dir = DATA_DIR

            removed_count = 0

            for filename in os.listdir(log_dir):
                # Only process log files (main log and rotated logs)
                if not (filename.startswith("bot.log") or filename.endswith(".log")):
                    continue

                file_path = os.path.join(log_dir, filename)

                try:
                    # Get file modification time in local timezone
                    mtime = datetime.fromtimestamp(
                        os.path.getmtime(file_path),
                        tz=TIMEZONE,
                    )

                    # Remove if older than cutoff
                    if mtime < cutoff:
                        os.remove(file_path)
                        removed_count += 1
                        logger.info(
                            "Removed old log: %s (modified: %s)",
                            filename,
                            mtime.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                except OSError as e:
                    logger.warning("Failed to remove log %s: %s", filename, e)

            if removed_count > 0:
                logger.info("Cleaned up %s old log file(s)", removed_count)
            else:
                logger.debug(
                    "No logs older than %s days found",
                    LOG_RETENTION_DAYS,
                )

        except Exception as e:
            logger.error("Log cleanup failed: %s", e, exc_info=True)

    def get_log_size(self) -> float:
        """
        Calculate total size of all log files.

        Returns:
            Total log size in MB.
        """
        try:
            total_bytes = 0
            log_dir = DATA_DIR

            for filename in os.listdir(log_dir):
                # Считаем размер основного лога и всех ротаций, как и в cleanup_old_logs
                if not (filename.startswith("bot.log") or filename.endswith(".log")):
                    continue

                file_path = os.path.join(log_dir, filename)
                try:
                    total_bytes += os.path.getsize(file_path)
                except OSError as e:
                    logger.debug(
                        "Failed to get size for log file %s: %s",
                        file_path,
                        e,
                    )

            return total_bytes / (1024 * 1024)  # Convert to MB
        except Exception as e:
            logger.error("Failed to calculate log size: %s", e, exc_info=True)
            return 0.0


# Global instance
log_service = LogService()
