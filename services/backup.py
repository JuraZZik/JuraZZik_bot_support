import os
import shutil
import logging
import tarfile
from datetime import datetime, timedelta
from typing import List, Tuple
from config import (
    BACKUP_DIR, DATA_DIR, DATA_FILE, BANNED_FILE,
    BACKUP_RETENTION_DAYS, BACKUP_FILE_PREFIX,
    BACKUP_ARCHIVE_TAR, TIMEZONE,
    BACKUP_FULL_PROJECT, BACKUP_FILE_LIST,
    BACKUP_EXCLUDE_PATTERNS,
    BACKUP_SEND_TO_TELEGRAM, BACKUP_MAX_SIZE_MB,
    BACKUP_ENABLED, BACKUP_SOURCE_DIR
)

logger = logging.getLogger(__name__)

class BackupService:
    def create_backup(self, backup_type: str = "manual") -> Tuple[str, dict]:
        """
        Create backup. Returns tuple (backup_path, backup_info)

        Args:
            backup_type: Type of backup - 'startup', 'shutdown', 'scheduled', 'manual'
        """
        if not BACKUP_ENABLED:
            logger.info("Backup is disabled by config")
            return "", {}

        try:
            timestamp = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
            backup_name = f"{BACKUP_FILE_PREFIX}{timestamp}"

            if BACKUP_FULL_PROJECT:
                backup_path, backup_info = self._create_full_backup(backup_name)
            else:
                backup_path, backup_info = self._create_files_backup(backup_name)

            # Add backup_type to info
            backup_info['backup_type'] = backup_type

            return backup_path, backup_info

        except Exception as e:
            logger.error(f"Backup creation failed: {e}", exc_info=True)
            raise

    def _should_exclude(self, path_str: str) -> bool:
        """Check exclusion patterns"""
        filename = path_str.split('/')[-1]

        for pattern in BACKUP_EXCLUDE_PATTERNS:
            # *.log, *.pyc → file extension
            if pattern.startswith("*."):
                if filename.endswith(pattern[1:]):
                    logger.debug(f"EXCLUDING: {path_str} (ext: {pattern})")
                    return True

            # backups, venv, __pycache__ → directory in path
            elif "/" + pattern + "/" in "/" + path_str + "/" or path_str.startswith(pattern + "/") or path_str == pattern:
                logger.debug(f"EXCLUDING: {path_str} (dir: {pattern})")
                return True

            # bot.log → exact name or starts with pattern (only if pattern > 1 char)
            elif filename == pattern or (len(pattern) > 1 and filename.startswith(pattern)):
                logger.debug(f"EXCLUDING: {path_str} (name: {pattern})")
                return True

        return False

    def _format_size(self, size_bytes: int) -> str:
        """Format file size"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"

    def _create_full_backup(self, backup_name: str) -> Tuple[str, dict]:
        """Create full project backup"""
        backup_path = os.path.join(BACKUP_DIR, f"{backup_name}.tar.gz")
        project_root = os.path.abspath(BACKUP_SOURCE_DIR)

        # Diagnostic logging
        logger.info(f"Backup source directory: {project_root}")
        logger.info(f"Directory exists: {os.path.exists(project_root)}")
        logger.info(f"Exclude patterns: {BACKUP_EXCLUDE_PATTERNS}")

        if os.path.exists(project_root):
            files_count = sum(len(files) for _, _, files in os.walk(project_root))
            logger.info(f"Total files in source directory: {files_count}")
        else:
            logger.error(f"Backup source directory does not exist: {project_root}")
            raise FileNotFoundError(f"Backup source directory not found: {project_root}")

        excluded_count = 0
        included_count = 0

        def filter_files(tarinfo):
            """Filter for excluding files and directories"""
            nonlocal excluded_count, included_count

            if self._should_exclude(tarinfo.name):
                excluded_count += 1
                return None

            logger.debug(f"INCLUDING: {tarinfo.name}")
            included_count += 1
            return tarinfo

        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(project_root, arcname=os.path.basename(project_root), filter=filter_files)
            files_added = len(tar.getmembers())

        logger.info(f"Full backup created: {backup_path}")
        logger.info(f"Files/dirs EXCLUDED: {excluded_count}")
        logger.info(f"Files/dirs INCLUDED: {included_count}")
        logger.info(f"Files/dirs added to backup: {files_added}")

        backup_size = os.path.getsize(backup_path)
        size_formatted = self._format_size(backup_size)
        logger.info(f"Backup file size: {backup_size} bytes ({size_formatted})")

        # Format backup info
        backup_info = {
            "type": "full",
            "source_dir": project_root,
            "excluded_patterns": ", ".join(BACKUP_EXCLUDE_PATTERNS),
            "files_in_archive": files_added,
            "size_bytes": backup_size,
            "size_formatted": size_formatted,
            "size_mb": backup_size / (1024 * 1024)
        }

        return backup_path, backup_info

    def _create_files_backup(self, backup_name: str) -> Tuple[str, dict]:
        """Create backup of selected files"""
        backup_path = os.path.join(BACKUP_DIR, f"{backup_name}.tar.gz")

        logger.info(f"Creating backup of selected files: {BACKUP_FILE_LIST}")

        files_added = 0
        with tarfile.open(backup_path, "w:gz") as tar:
            for filename in BACKUP_FILE_LIST:
                file_path = os.path.join(DATA_DIR, filename)
                if os.path.isfile(file_path):
                    tar.add(file_path, arcname=filename)
                    files_added += 1
                    logger.debug(f"Added to backup: {filename}")
                else:
                    logger.warning(f"File {file_path} not found and skipped")

        logger.info(f"Files backup created: {backup_path}")
        logger.info(f"Files added to backup: {files_added}")

        backup_size = os.path.getsize(backup_path)
        size_formatted = self._format_size(backup_size)
        logger.info(f"Backup file size: {backup_size} bytes ({size_formatted})")

        # Format backup info
        backup_info = {
            "type": "files",
            "files": ", ".join(BACKUP_FILE_LIST),
            "files_in_archive": files_added,
            "size_bytes": backup_size,
            "size_formatted": size_formatted,
            "size_mb": backup_size / (1024 * 1024)
        }

        return backup_path, backup_info

    async def send_backup_to_telegram(self, backup_path: str, backup_info: dict):
        """Send backup file to Telegram if enabled"""
        if not BACKUP_SEND_TO_TELEGRAM:
            logger.debug("Sending backup to Telegram is disabled")
            return

        if not backup_path or not os.path.exists(backup_path):
            logger.warning(f"Backup file not found: {backup_path}")
            return

        try:
            from services.alerts import alert_service
            from locales import get_text
            from utils.locale_helper import get_admin_language

            # Check if alert service is configured
            if not alert_service._bot:
                logger.warning("Alert service not configured, cannot send backup")
                return

            # Get admin language for proper translations
            admin_lang = get_admin_language()

            # Get filename
            filename = os.path.basename(backup_path)

            # Get backup type and format caption header
            backup_type = backup_info.get('backup_type', 'manual')

            caption_map = {
                'startup': 'backup_captions.startup',
                'shutdown': 'backup_captions.shutdown',
                'scheduled': 'backup_captions.scheduled',
                'manual': 'backup_captions.manual'
            }

            caption_key = caption_map.get(backup_type, 'backup_captions.manual')

            # Use get_text with explicit lang parameter
            try:
                caption_header = get_text(caption_key, lang=admin_lang)
            except:
                # Fallback if translation not found
                caption_header = f"📦 Backup ({backup_type})"

            # Build detailed caption with translations
            caption = f"{caption_header}\n\n"
            caption += f"{filename} ({backup_info.get('size_formatted', 'unknown')})\n\n"

            # Add directory info (for full backups)
            if backup_info.get('source_dir'):
                try:
                    dir_label = get_text('backup_details.directory', lang=admin_lang)
                except:
                    dir_label = "Directory"
                caption += f"📁 {dir_label}: {backup_info.get('source_dir')}\n"

            # Add excluded patterns
            if backup_info.get('excluded_patterns'):
                try:
                    excl_label = get_text('backup_details.excluded', lang=admin_lang)
                except:
                    excl_label = "Excluded"
                caption += f"❌ {excl_label}: {backup_info.get('excluded_patterns')}\n"

            # Add files and size with translations
            try:
                files_label = get_text('backup_details.files', lang=admin_lang)
                size_label = get_text('backup_details.size', lang=admin_lang)
                file_label = get_text('backup_details.file', lang=admin_lang)
            except:
                # Fallback to English
                files_label = "Files"
                size_label = "Size"
                file_label = "File"

            caption += f"📦 {files_label}: {backup_info.get('files_in_archive', 0)}\n"
            caption += f"💾 {size_label}: {backup_info.get('size_formatted', 'unknown')}\n"
            caption += f"📝 {file_label}: {filename}"

            # Send using send_backup_file method
            await alert_service.send_backup_file(backup_path, caption)

            logger.info(f"Backup sent to Telegram: {os.path.basename(backup_path)}")

        except Exception as e:
            logger.error(f"Failed to send backup to Telegram: {e}", exc_info=True)

    def get_backup_size_mb(self, backup_path: str) -> float:
        """Get backup size in MB"""
        if os.path.isfile(backup_path):
            return os.path.getsize(backup_path) / (1024 * 1024)
        elif os.path.isdir(backup_path):
            total = sum(os.path.getsize(os.path.join(dirpath, filename))
                       for dirpath, _, filenames in os.walk(backup_path)
                       for filename in filenames)
            return total / (1024 * 1024)
        return 0

    def cleanup_old_backups(self):
        """Remove old backups"""
        try:
            cutoff = datetime.now(TIMEZONE) - timedelta(days=BACKUP_RETENTION_DAYS)
            removed_count = 0

            for item in os.listdir(BACKUP_DIR):
                item_path = os.path.join(BACKUP_DIR, item)

                if not item.startswith(BACKUP_FILE_PREFIX):
                    continue

                mtime = datetime.fromtimestamp(os.path.getmtime(item_path), tz=TIMEZONE)

                if mtime < cutoff:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        removed_count += 1
                        logger.info(f"Removed old backup: {item}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        removed_count += 1
                        logger.info(f"Removed old backup directory: {item}")

            if removed_count > 0:
                logger.info(f"Cleanup completed: {removed_count} old backup(s) removed")
            else:
                logger.debug(f"No old backups to remove (retention: {BACKUP_RETENTION_DAYS} days)")

        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}", exc_info=True)

    def list_backups(self) -> List[str]:
        """Get list of backups"""
        try:
            backups = []
            for item in os.listdir(BACKUP_DIR):
                if item.startswith(BACKUP_FILE_PREFIX):
                    backups.append(item)
            return sorted(backups, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list backups: {e}", exc_info=True)
            return []

# Global instance
backup_service = BackupService()
