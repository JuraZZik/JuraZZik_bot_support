import logging
import os
import asyncio
from zoneinfo import ZoneInfo
from config import TIMEZONE
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from config import (
    ADMIN_ID, START_ALERT, ALERT_CHAT_ID, ALERT_TOPIC_ID,
    ALERT_PARSE_MODE, BOT_NAME, BOT_VERSION, BOT_BUILD_DATE
)
from storage.data_manager import data_manager
from locales import _, set_locale

logger = logging.getLogger(__name__)

class AlertService:
    def __init__(self):
        self._bot = None

    def set_bot(self, bot: Bot):
        """Set bot for sending alerts"""
        self._bot = bot

    def _load_admin_locale(self):
        """Load admin's locale"""
        try:
            user_data = data_manager.get_user_data(ADMIN_ID)
            admin_locale = user_data.get("locale", "ru")
            set_locale(admin_locale)
        except Exception as e:
            logger.warning(f"Failed to load admin locale, using default: {e}")
            set_locale("ru")

    async def send_alert(self, text: str):
        """Send text alert to admin"""
        if not self._bot:
            logger.warning("Bot not configured for alerts")
            return

        chat_id = ALERT_CHAT_ID if ALERT_CHAT_ID else ADMIN_ID

        if not chat_id:
            logger.warning("ALERT_CHAT_ID and ADMIN_ID not configured for alerts")
            return

        try:
            kwargs = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": ALERT_PARSE_MODE
            }
            if ALERT_TOPIC_ID:
                kwargs["message_thread_id"] = ALERT_TOPIC_ID

            await self._bot.send_message(**kwargs)
            logger.info(f"Alert sent to {chat_id} (topic: {ALERT_TOPIC_ID}): {text[:50]}...")
        except TelegramError as e:
            logger.error(f"Failed to send alert to {chat_id}: {e}")

    async def send_backup_file(self, backup_path: str, caption: str):
        """Send backup file to Telegram"""
        from config import BACKUP_SEND_TO_TELEGRAM, BACKUP_MAX_SIZE_MB
        from services.backup import backup_service

        if not BACKUP_SEND_TO_TELEGRAM:
            logger.debug("Backup send to Telegram disabled")
            return

        try:
            size_mb = backup_service.get_backup_size_mb(backup_path)

            if size_mb > BACKUP_MAX_SIZE_MB:
                logger.warning(f"Backup too large for Telegram: {size_mb:.1f}MB > {BACKUP_MAX_SIZE_MB}MB")
                await self.send_alert(f"⚠️ Backup too large to send: {size_mb:.1f}MB")
                return

            chat_id = ALERT_CHAT_ID if ALERT_CHAT_ID else ADMIN_ID

            if not chat_id:
                logger.warning("No chat_id for backup file")
                return

            logger.info(f"Sending backup file: {os.path.basename(backup_path)} ({size_mb:.2f}MB)")

            with open(backup_path, 'rb') as f:
                kwargs = {
                    "chat_id": chat_id,
                    "document": f,
                    "caption": caption,
                    "filename": os.path.basename(backup_path),
                    "parse_mode": None  # No HTML parsing for caption - prevents < > issues
                }
                if ALERT_TOPIC_ID:
                    kwargs["message_thread_id"] = ALERT_TOPIC_ID

                await self._bot.send_document(**kwargs)

            logger.info(f"Backup file sent to Telegram: {os.path.basename(backup_path)}")
        except Exception as e:
            logger.error(f"Failed to send backup file: {e}", exc_info=True)
            await self.send_alert(f"❌ Backup send error: {str(e)}")

    async def send_ticket_card(self, ticket_id: str, action: str = "new"):
        """
        Send ticket card to admin
        action: 'new' - new ticket, 'message' - new message
        """
        if not self._bot or not ADMIN_ID:
            logger.warning("Bot or ADMIN_ID not configured for alerts")
            return

        try:
            from services.tickets import ticket_service
            from utils.formatters import format_ticket_card

            ticket = ticket_service.get_ticket(ticket_id)
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return

            text = format_ticket_card(ticket)

            if action == "new":
                text = f"🆕 NEW TICKET\n\n{text}"
            elif action == "message":
                text = f"💬 NEW MESSAGE\n\n{text}"

            buttons = []

            if ticket.status == "new":
                buttons.append([InlineKeyboardButton("✅ Take in progress", callback_data=f"take:{ticket_id}")])
            elif ticket.status == "working":
                buttons.append([InlineKeyboardButton("💬 Reply", callback_data=f"reply:{ticket_id}")])
                buttons.append([InlineKeyboardButton("✅ Close", callback_data=f"close:{ticket_id}")])

            buttons.append([InlineKeyboardButton("📥 To inbox", callback_data="admin_inbox")])

            keyboard = InlineKeyboardMarkup(buttons)

            await self._bot.send_message(
                chat_id=ADMIN_ID,
                text=text,
                reply_markup=keyboard
            )
            logger.info(f"Ticket card sent to admin: {ticket_id}")

        except Exception as e:
            logger.error(f"Failed to send ticket card: {e}", exc_info=True)

    async def send_startup_alert(self):
        """Bot startup notification"""
        if not START_ALERT:
            return

        from datetime import datetime
        from config import DATA_DIR, BACKUP_DIR

        self._load_admin_locale()

        now = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M:%S")
        stats = data_manager.get_stats()

        def check_path(path):
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

    async def send_backup_alert(self, backup_info: str):
        """Backup creation notification"""
        self._load_admin_locale()
        await self.send_alert(_("alerts.backup_created", info=backup_info))

    async def send_ticket_auto_closed_alert(self, ticket_id: str, hours: int):
        """Auto-closed ticket notification"""
        self._load_admin_locale()
        await self.send_alert(
            _("alerts.ticket_auto_closed", ticket_id=ticket_id, hours=hours)
        )

# Global instance
alert_service = AlertService()
