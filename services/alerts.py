import logging
import os
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from config import (
    TIMEZONE,
    ADMIN_ID,
    START_ALERT,
    SHUTDOWN_ALERT,
    ALERT_CHAT_ID,
    ALERT_TOPIC_ID,
    ALERT_PARSE_MODE,
    BOT_NAME,
    BOT_VERSION,
    BOT_BUILD_DATE,
    DATA_DIR,
    BACKUP_DIR,
)
from storage.data_manager import data_manager
from locales import _, set_locale
from utils.locale_helper import get_admin_language, get_user_language

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self) -> None:
        self._bot: Optional[Bot] = None

    # ---------- bot wiring ----------

    def set_bot(self, bot: Bot) -> None:
        """Set bot for sending alerts."""
        self._bot = bot

    def _ensure_bot(self) -> bool:
        if not self._bot:
            logger.warning("Bot not configured for alerts")
            return False
        return True

    # ---------- locale helpers ----------

    def _load_admin_locale(self) -> None:
        """Set global locale to admin's preferred language."""
        try:
            user_data = data_manager.get_user_data(ADMIN_ID)
            admin_locale = user_data.get("locale", "ru")
            set_locale(admin_locale)
        except Exception as e:
            logger.warning("Failed to load admin locale, using default: %s", e)
            set_locale("ru")

    # ---------- low-level send wrappers ----------

    async def send_alert(self, text: str) -> None:
        """Send text alert to admin/alert chat."""
        if not self._ensure_bot():
            return

        chat_id = ALERT_CHAT_ID if ALERT_CHAT_ID else ADMIN_ID
        if not chat_id:
            logger.warning("ALERT_CHAT_ID and ADMIN_ID not configured for alerts")
            return

        try:
            kwargs = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": ALERT_PARSE_MODE,
            }
            if ALERT_TOPIC_ID:
                kwargs["message_thread_id"] = ALERT_TOPIC_ID

            await self._bot.send_message(**kwargs)
            logger.info(
                "Alert sent to %s (topic: %s): %s...",
                chat_id,
                ALERT_TOPIC_ID,
                text[:50],
            )
        except TelegramError as e:
            logger.error("Failed to send alert to %s: %s", chat_id, e)

    async def send_backup_file(self, backup_path: str, caption: str) -> None:
        """Send backup file to Telegram (alert chat/admin)."""
        from config import BACKUP_SEND_TO_TELEGRAM, BACKUP_MAX_SIZE_MB
        from services.backup import backup_service

        if not BACKUP_SEND_TO_TELEGRAM:
            logger.debug("Backup send to Telegram disabled")
            return

        if not self._ensure_bot():
            return

        try:
            size_mb = backup_service.get_backup_size_mb(backup_path)

            if size_mb > BACKUP_MAX_SIZE_MB:
                logger.warning(
                    "Backup too large for Telegram: %.1fMB > %dMB",
                    size_mb,
                    BACKUP_MAX_SIZE_MB,
                )
                await self.send_alert(f"⚠️ Backup too large to send: {size_mb:.1f}MB")
                return

            chat_id = ALERT_CHAT_ID if ALERT_CHAT_ID else ADMIN_ID
            if not chat_id:
                logger.warning("No chat_id for backup file")
                return

            logger.info(
                "Sending backup file: %s (%.2fMB)",
                os.path.basename(backup_path),
                size_mb,
            )

            with open(backup_path, "rb") as f:
                kwargs = {
                    "chat_id": chat_id,
                    "document": f,
                    "caption": caption,
                    "filename": os.path.basename(backup_path),
                    # caption без parse_mode, чтобы не ломать < >
                    "parse_mode": None,
                }
                if ALERT_TOPIC_ID:
                    kwargs["message_thread_id"] = ALERT_TOPIC_ID

                await self._bot.send_document(**kwargs)

            logger.info(
                "Backup file sent to Telegram: %s",
                os.path.basename(backup_path),
            )
        except Exception as e:
            logger.error("Failed to send backup file: %s", e, exc_info=True)
            await self.send_alert(f"❌ Backup send error: {str(e)}")

    async def send_user_message(self, user_id: int, text: str) -> None:
        """Utility: send plain text message to given user."""
        if not self._ensure_bot():
            return
        try:
            await self._bot.send_message(chat_id=user_id, text=text)
        except TelegramError as e:
            logger.error(
                "Failed to send user message to %s: %s", user_id, e, exc_info=True
            )

    # ---------- ticket-related alerts ----------

    async def send_ticket_card(self, ticket_id: str, action: str = "new") -> None:
        """
        Send ticket card to admin.
        action: 'new' - new ticket, 'message' - new message
        """
        if not self._ensure_bot() or not ADMIN_ID:
            logger.warning("Bot or ADMIN_ID not configured for alerts")
            return

        try:
            from services.tickets import ticket_service
            from utils.formatters import format_ticket_card
            from locales import get_text

            ticket = ticket_service.get_ticket(ticket_id)
            if not ticket:
                logger.error("Ticket %s not found", ticket_id)
                return

            admin_lang = get_admin_language()
            text = format_ticket_card(ticket)

            if action == "new":
                text = f"{get_text('notifications.new_ticket', lang=admin_lang)}\n\n{text}"
            elif action == "message":
                text = f"{get_text('notifications.new_message', lang=admin_lang)}\n\n{text}"

            buttons: list[list[InlineKeyboardButton]] = []

            if ticket.status == "new":
                buttons.append(
                    [
                        InlineKeyboardButton(
                            get_text("buttons.take", lang=admin_lang),
                            callback_data=f"take:{ticket_id}",
                        ),
                        InlineKeyboardButton(
                            get_text("buttons.close", lang=admin_lang),
                            callback_data=f"close:{ticket_id}",
                        ),
                    ]
                )
            elif ticket.status == "working":
                buttons.append(
                    [
                        InlineKeyboardButton(
                            get_text("buttons.reply", lang=admin_lang),
                            callback_data=f"reply:{ticket_id}",
                        ),
                        InlineKeyboardButton(
                            get_text("buttons.close", lang=admin_lang),
                            callback_data=f"close:{ticket_id}",
                        ),
                    ]
                )

            buttons.append(
                [
                    InlineKeyboardButton(
                        get_text("buttons.inbox", lang=admin_lang),
                        callback_data="admin_inbox",
                    )
                ]
            )

            keyboard = InlineKeyboardMarkup(buttons)

            await self._bot.send_message(
                chat_id=ADMIN_ID,
                text=text,
                reply_markup=keyboard,
            )
            logger.info("Ticket card sent to admin: %s", ticket_id)

        except Exception as e:
            logger.error("Failed to send ticket card: %s", e, exc_info=True)

    # ---------- startup & backup alerts ----------

    async def send_startup_alert(self) -> None:
        """Bot startup notification."""
        if not START_ALERT:
            logger.info("Startup alert suppressed by START_ALERT flag")
            return

        from datetime import datetime

        self._load_admin_locale()

        now = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M:%S")
        stats = data_manager.get_stats()

        def check_path(path: str) -> str:
            if os.path.exists(path):
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    return f"✅ ({size / 1024:.1f} KB)"
                else:
                    count = len(os.listdir(path))
                    files_word = "files"
                    return f"✅ ({count} {files_word})"
            return "❌"

        data_json = os.path.join(DATA_DIR, "data.json")
        log_file = os.path.join(DATA_DIR, "bot.log")

        text = (
            f"{_('alerts.bot_started')}\n"
            f"🤖 Bot: {BOT_NAME}\n"
            f"🔖 Version: {BOT_VERSION}\n"
            f"📅 Build: {BOT_BUILD_DATE}\n\n"
            f"{_('alerts.time', time=now)}\n\n"
            f"{_('alerts.files')}\n"
            f"{_('alerts.file_data', status=check_path(data_json))}\n"
            f"{_('alerts.file_log', status=check_path(log_file))}\n"
            f"{_('alerts.file_backups', status=check_path(BACKUP_DIR))}\n\n"
            f"{_('alerts.stats')}\n"
            f"{_('alerts.stat_active', count=stats['active_tickets'])}\n"
            f"{_('alerts.stat_total', count=stats['total_tickets'])}\n"
            f"{_('alerts.stat_users', count=stats['total_users'])}"
        )

        await self.send_alert(text)

    async def send_shutdown_alert(self) -> None:
        """Bot shutdown notification."""
        if not SHUTDOWN_ALERT:
            logger.info("Shutdown alert suppressed by SHUTDOWN_ALERT flag")
            return

        from datetime import datetime

        self._load_admin_locale()

        now = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M:%S")
        stats = data_manager.get_stats()

        text = (
            f"{_('alerts.bot_stopped')}\n"
            f"🤖 Bot: {BOT_NAME}\n"
            f"🔖 Version: {BOT_VERSION}\n"
            f"📅 Build: {BOT_BUILD_DATE}\n\n"
            f"{_('alerts.time', time=now)}\n\n"
            f"{_('alerts.stats')}\n"
            f"{_('alerts.stat_active', count=stats['active_tickets'])}\n"
            f"{_('alerts.stat_total', count=stats['total_tickets'])}\n"
            f"{_('alerts.stat_users', count=stats['total_users'])}"
        )

        await self.send_alert(text)

    async def send_backup_alert(self, backup_info: str) -> None:
        """Backup creation notification."""
        self._load_admin_locale()
        await self.send_alert(_("alerts.backup_created", info=backup_info))

    async def send_ticket_auto_closed_alert(self, ticket_id: str, hours: int) -> None:
        """Auto-closed ticket notification (simple text alert)."""
        self._load_admin_locale()
        await self.send_alert(
            _("alerts.ticket_auto_closed", ticket_id=ticket_id, hours=hours)
        )


# Global instance
alert_service = AlertService()
