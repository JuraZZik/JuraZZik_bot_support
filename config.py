#!/usr/bin/env python3
import os
import logging
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from logging.handlers import RotatingFileHandler

from colorlog import ColoredFormatter

# ========================================
# BOT INFORMATION
# ========================================
BOT_NAME = "JuraZZik"
BOT_VERSION = "2.8.0"
BOT_BUILD_DATE = "2025-11-22"

# ========================================
# ENVIRONMENT VARIABLES
# ========================================

# Bot Token
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment")

# Admin ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if ADMIN_ID <= 0:
    raise ValueError("ADMIN_ID not set or invalid in environment")

# Other bot username (optional)
OTHER_BOT_USERNAME = os.getenv("OTHER_BOT_USERNAME", None)

# Default locale - MUST be set in environment
AVAILABLE_LOCALES = ["ru", "en"]
DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE")
if not DEFAULT_LOCALE:
    raise ValueError(
        "DEFAULT_LOCALE not set in environment. Please set DEFAULT_LOCALE in .env file (ru or en)"
    )
if DEFAULT_LOCALE not in AVAILABLE_LOCALES:
    raise ValueError(
        f"DEFAULT_LOCALE '{DEFAULT_LOCALE}' not in {AVAILABLE_LOCALES}. Set in .env"
    )

# ========== BASIC SETTINGS ==========

FEEDBACK_COOLDOWN_ENABLED = os.getenv("FEEDBACK_COOLDOWN_ENABLED", "true").lower() == "true"
FEEDBACK_COOLDOWN_HOURS = int(os.getenv("FEEDBACK_COOLDOWN_HOURS", "24"))

# ========== ALERT SETTINGS ==========

ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID", None)
if ALERT_CHAT_ID:
    try:
        ALERT_CHAT_ID = int(ALERT_CHAT_ID)
    except ValueError:
        raise ValueError("ALERT_CHAT_ID must be a valid integer")

ALERT_TOPIC_ID = os.getenv("ALERT_TOPIC_ID", None)
if ALERT_TOPIC_ID:
    try:
        ALERT_TOPIC_ID = int(ALERT_TOPIC_ID)
    except ValueError:
        raise ValueError("ALERT_TOPIC_ID must be a valid integer")

# IMPORTANT: START_ALERT/SHUTDOWN_ALERT are booleans (not text)
START_ALERT = os.getenv("START_ALERT", "true").lower() == "true"
SHUTDOWN_ALERT = os.getenv("SHUTDOWN_ALERT", "false").lower() == "true"
ALERT_PARSE_MODE = os.getenv("ALERT_PARSE_MODE", "HTML")
ALERT_THROTTLE_SEC = int(os.getenv("ALERT_THROTTLE_SEC", "0"))

# ========== FILE PATHS ==========

DATA_DIR = os.getenv("DATA_DIR", "./bot_data")
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "data.json")
BANNED_FILE = os.path.join(DATA_DIR, "banned.json")
LOG_FILE = os.path.join(DATA_DIR, "bot.log")

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)
BACKUP_SOURCE_DIR = os.getenv("BACKUP_SOURCE_DIR", ".")

# ========== UI SETTINGS ==========

PAGE_SIZE = int(os.getenv("PAGE_SIZE", "10"))
BANS_PAGE_SIZE = int(os.getenv("BANS_PAGE_SIZE", "10"))
ASK_MIN_LENGTH = int(os.getenv("ASK_MIN_LENGTH", "10"))
AUTO_CLOSE_AFTER_HOURS = int(os.getenv("AUTO_CLOSE_AFTER_HOURS", "24"))
ENABLE_MEDIA_FROM_USERS = os.getenv("ENABLE_MEDIA_FROM_USERS", "false").lower() == "true"
INBOX_PREVIEW_LEN = int(os.getenv("INBOX_PREVIEW_LEN", "60"))
MAX_CARD_LENGTH = int(os.getenv("MAX_CARD_LENGTH", "4000"))
RATING_ENABLED = os.getenv("RATING_ENABLED", "true").lower() == "true"

# ========== AUTOMATION ==========

AUTO_SAVE_INTERVAL = int(os.getenv("AUTO_SAVE_INTERVAL", "300"))

# ========== BAN DETECTION & MANAGEMENT ==========

BAN_NAME_LINK_CHECK = os.getenv("BAN_NAME_LINK_CHECK", "false").lower() == "true"
BAN_DEFAULT_REASON = os.getenv("BAN_DEFAULT_REASON", "Violation of rules")
BAN_ON_NAME_LINK = os.getenv("BAN_ON_NAME_LINK", "false").lower() == "true"
NAME_LINK_PATTERN = os.getenv(
    "NAME_LINK_PATTERN",
    r"https?://|www\.|\.ru|\.com|\.org|\.io|@\w+|t\.me",
)

# ========== TICKET SETTINGS ==========

TICKET_HISTORY_LIMIT = int(os.getenv("TICKET_HISTORY_LIMIT", "10"))

# ========== BACKUP CONFIGURATION ==========

BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "false").lower() == "true"
BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
BACKUP_FILE_PREFIX = os.getenv("BACKUP_FILE_PREFIX", "backup")
BACKUP_FULL_PROJECT = os.getenv("BACKUP_FULL_PROJECT", "false").lower() == "true"

BACKUP_FILE_LIST = os.getenv("BACKUP_FILE_LIST", "data.json,banned.json")
BACKUP_FILE_LIST = [f.strip() for f in BACKUP_FILE_LIST.split(",")] if BACKUP_FILE_LIST else []

BACKUP_EXCLUDE_PATTERNS = [
    p.strip()
    for p in os.getenv(
        "BACKUP_EXCLUDE_PATTERNS",
        "backups,bot.log,__pycache__,.git,.pyc,venv,*.log",
    ).split(",")
    if p.strip()
]

BACKUP_SEND_TO_TELEGRAM = os.getenv("BACKUP_SEND_TO_TELEGRAM", "false").lower() == "true"
BACKUP_MAX_SIZE_MB = int(os.getenv("BACKUP_MAX_SIZE_MB", "100"))
BACKUP_ARCHIVE_TAR = True
STORAGE_BACKUP_INTERVAL_HOURS = int(os.getenv("STORAGE_BACKUP_INTERVAL_HOURS", "24"))
BACKUP_ON_START = os.getenv("BACKUP_ON_START", "false").lower() == "true"

# ========== LOGGING SETTINGS ==========

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_SIZE_MB = int(os.getenv("LOG_MAX_SIZE_MB", "10"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
LOG_CLEANUP_ENABLED = os.getenv("LOG_CLEANUP_ENABLED", "false").lower() == "true"
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "7"))

DEBUG = os.getenv("DEBUG", "0") == "1"

ERROR_ALERTS_ENABLED = os.getenv("ERROR_ALERTS_ENABLED", "false").lower() == "true"
ERROR_ALERT_THROTTLE_SEC = int(os.getenv("ERROR_ALERT_THROTTLE_SEC", "60"))

# ========== TIMEZONE CONFIGURATION ==========

TIMEZONE_STR = os.getenv("TIMEZONE", "UTC")
try:
    TIMEZONE = ZoneInfo(TIMEZONE_STR)
except Exception:
    raise ValueError(
        f"Invalid TIMEZONE: {TIMEZONE_STR}. Must be a valid IANA timezone (e.g., 'UTC', 'Europe/Moscow')"
    )

# Legacy/optional offset info (currently not used in code)
TZ_OFFSET = os.getenv("TZ_OFFSET", "UTC")

# ========== NETWORK & API SETTINGS ==========

BOT_API_BASE = os.getenv("BOT_API_BASE", "https://api.telegram.org")
USE_LOCAL_BOT_API = os.getenv("USE_LOCAL_BOT_API", "false").lower() == "true"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_SEC = int(os.getenv("RETRY_BACKOFF_SEC", "2"))


# ========================================
# TELEGRAM ERROR HANDLER
# ========================================

class TelegramErrorHandler(logging.Handler):
    """Send critical errors to Telegram (thread-safe for asyncio)."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self._last_error_time: dict[str, datetime] = {}
        self._throttle_seconds = ERROR_ALERT_THROTTLE_SEC
        self._enabled = ERROR_ALERTS_ENABLED
        self._loop: asyncio.AbstractEventLoop | None = None
        self._warned_unconfigured = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach running event loop from PTB Application/post_init."""
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        if not self._enabled:
            return

        if self._loop is None:
            if not self._warned_unconfigured:
                self._warned_unconfigured = True
                logging.getLogger(__name__).warning(
                    "TelegramErrorHandler has no event loop; error alerts will not be sent"
                )
            return

        try:
            try:
                from services.alerts import alert_service
            except ImportError:
                return

            if not getattr(alert_service, "_bot", None):
                return

            error_key = f"{record.levelname}:{record.msg}"
            now = datetime.now()

            last_time = self._last_error_time.get(error_key)
            if last_time and now - last_time < timedelta(seconds=self._throttle_seconds):
                return

            self._last_error_time[error_key] = now

            emoji = "🔴" if record.levelno >= logging.CRITICAL else "⚠️"
            text = (
                f"{emoji} {record.levelname}\n"
                f"📂 Module: {record.name}\n"
                f"📝 {record.getMessage()}\n"
                f"🕒 {datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M:%S')}"
            )

            if record.exc_info:
                import traceback

                tb = "".join(traceback.format_exception(*record.exc_info))
                if len(tb) > 500:
                    tb = tb[:500] + "\n..."
                text += f"\n\n🐛 Traceback:\n<code>{tb}</code>"

            async def _send() -> None:
                await alert_service.send_alert(text)

            try:
                asyncio.run_coroutine_threadsafe(_send(), self._loop)
            except Exception:
                pass

        except Exception:
            pass


# ========================================
# LOGGING SETUP
# ========================================

def setup_logging() -> None:
    """Configure logging system."""
    # Формат для файла (без цветов, выровненные колонки)
    file_log_format = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Формат для консоли (с цветами + те же колонки)
    console_log_format = "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    file_formatter = logging.Formatter(file_log_format, datefmt=date_format)

    console_formatter = ColoredFormatter(
        console_log_format,
        datefmt=date_format,
        log_colors={
            "DEBUG": "reset",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(level)

    # Console handler (цветной)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(level)

    handlers: list[logging.Handler] = [file_handler, console_handler]

    if ERROR_ALERTS_ENABLED:
        handlers.append(TelegramErrorHandler())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    # Урезаем болтовню сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)


# ========================================
# APPLICATION LIFECYCLE
# ========================================

async def post_init(application):
    """Initialize after bot startup: menus, alert service, scheduler, startup backup & alerts."""
    # Setup bot menu
    logger.info("Setting up bot menu...")
    try:
        from utils.menu import setup_bot_menu
        await setup_bot_menu(application)
        logger.info("Bot menu configured successfully")
    except Exception as e:
        logger.error(f"Failed to setup bot menu: {e}", exc_info=True)

    # Configure alert service
    try:
        from services.alerts import alert_service
        alert_service.set_bot(application.bot)
        logger.info("Alert service bot configured")
    except Exception as e:
        logger.error(f"Failed to configure alert service: {e}", exc_info=True)

    # Attach event loop to TelegramErrorHandler
    try:
        loop = asyncio.get_running_loop()
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, TelegramErrorHandler):
                handler.set_loop(loop)
                logger.info("TelegramErrorHandler loop configured")
    except Exception as e:
        logger.error(
            f"Failed to configure TelegramErrorHandler loop: {e}",
            exc_info=True,
        )

    # Start scheduler
    from services.scheduler import scheduler_service
    from services.ticket_auto_close import auto_close_inactive_tickets

    await scheduler_service.start()
    logger.info("Scheduler service started")

    try:
        async def cleanup_logs_async():
            from services.logs import log_service
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, log_service.cleanup_old_logs)

        await scheduler_service.add_job(
            "cleanup_logs",
            cleanup_logs_async,
            3600,
            run_immediately=False,
        )
        logger.info("Added job: cleanup_logs (interval: 3600s)")

        async def backup_async():
            from services.backup import backup_service
            loop = asyncio.get_event_loop()
            backup_path, backup_info = await loop.run_in_executor(
                None,
                backup_service.create_backup,
                "scheduled",
            )

            if backup_path and BACKUP_SEND_TO_TELEGRAM:
                await backup_service.send_backup_to_telegram(
                    backup_path, backup_info
                )

        backup_interval = STORAGE_BACKUP_INTERVAL_HOURS * 3600
        await scheduler_service.add_job(
            "daily_backup",
            backup_async,
            backup_interval,
            run_immediately=False,
        )
        logger.info(
            "Added job: daily_backup (interval: %ss / %sh)",
            backup_interval,
            STORAGE_BACKUP_INTERVAL_HOURS,
        )

        async def cleanup_backups_async():
            from services.backup import backup_service
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, backup_service.cleanup_old_backups)

        await scheduler_service.add_job(
            "cleanup_backups",
            cleanup_backups_async,
            86400,
            run_immediately=False,
        )
        logger.info("Added job: cleanup_backups (interval: 86400s)")

        await scheduler_service.add_job(
            "auto_close_tickets",
            auto_close_inactive_tickets,
            3600,
            run_immediately=True,
        )
        logger.info("Added job: auto_close_tickets (interval: 3600s)")
    except Exception as e:
        logger.error(f"Failed to add scheduler jobs: {e}", exc_info=True)

    # Startup backup if enabled
    if BACKUP_ON_START and BACKUP_ENABLED:
        try:
            from services.backup import backup_service
            loop = asyncio.get_event_loop()
            backup_path, backup_info = await loop.run_in_executor(
                None,
                backup_service.create_backup,
                "startup",
            )
            logger.info("Startup backup created successfully")

            if backup_path and BACKUP_SEND_TO_TELEGRAM:
                await backup_service.send_backup_to_telegram(
                    backup_path, backup_info
                )
        except Exception as e:
            logger.error(f"Failed to create startup backup: {e}", exc_info=True)

    # Startup alert if enabled
    if START_ALERT:
        try:
            from services.alerts import alert_service
            await alert_service.send_startup_alert()
            logger.info("Startup alert sent successfully")
        except Exception as e:
            logger.error(
                f"Failed to send startup alert: {e}",
                exc_info=True,
            )
    else:
        logger.info("Startup alert is disabled by START_ALERT flag")


async def post_shutdown(application):
    """Actions on bot shutdown: stop scheduler, persist data, optional shutdown alert."""
    from services.scheduler import scheduler_service
    await scheduler_service.stop()
    logger.info("Scheduler service stopped")

    from storage.data_manager import data_manager
    data_manager.save()
    logger.info("Data saved on shutdown")

    # Shutdown alert if enabled
    if SHUTDOWN_ALERT:
        try:
            from services.alerts import alert_service
            await alert_service.send_shutdown_alert()
            logger.info("Shutdown alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send shutdown alert: {e}", exc_info=True)
    else:
        logger.info("Shutdown alert is disabled by SHUTDOWN_ALERT flag")

    logger.info("Shutdown complete")


logger.info(
    "%s v%s (build %s) - configuration loaded",
    BOT_NAME,
    BOT_VERSION,
    BOT_BUILD_DATE,
)
