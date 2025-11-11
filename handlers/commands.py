import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID, BACKUP_ENABLED
from handlers.user import ask_question_handler, suggestion_handler, review_handler
from handlers.admin import inbox_handler, stats_handler, settings_handler, home_handler
from utils.locale_helper import get_admin_language
from locales import get_text

logger = logging.getLogger(__name__)

async def question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /question"""
    await ask_question_handler(update, context)

async def suggestion_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /suggestion"""
    await suggestion_handler(update, context)

async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /review"""
    await review_handler(update, context)

async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /inbox"""
    await inbox_handler(update, context)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /stats"""
    await stats_handler(update, context)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /settings"""
    await settings_handler(update, context)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /admin - show admin main menu"""
    user = update.effective_user

    if user.id != ADMIN_ID:
        return

    await home_handler(update, context)

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /backup - create manual backup"""
    user = update.effective_user
    user_lang = get_admin_language()

    # Check if user is admin
    if user.id != ADMIN_ID:
        return

    # Check if backup is enabled
    if not BACKUP_ENABLED:
        await update.message.reply_text(
            get_text("messages.backup_disabled_full", lang=user_lang)
        )
        return

    try:
        from services.backup import backup_service
        from config import BACKUP_SEND_TO_TELEGRAM, BACKUP_MAX_SIZE_MB
        import os

        # Create backup
        await update.message.reply_text("⏳ Creating backup...")

        backup_path, backup_info = backup_service.create_backup("manual")

        if not backup_path:
            await update.message.reply_text(
                get_text("admin.backup_failed", lang=user_lang, error="Backup creation failed")
            )
            return

        # Get backup size
        size_mb = backup_info.get('size_mb', 0)
        size_formatted = backup_info.get('size_formatted', 'unknown')
        filename = os.path.basename(backup_path)

        # Send backup to Telegram if enabled and size is acceptable
        if BACKUP_SEND_TO_TELEGRAM and size_mb <= BACKUP_MAX_SIZE_MB:
            await backup_service.send_backup_to_telegram(backup_path, backup_info)
            await update.message.reply_text(
                get_text("admin.backup_created_sent", lang=user_lang, 
                        filename=filename, size=size_formatted)
            )
        else:
            # Just save on server
            await update.message.reply_text(
                get_text("admin.backup_created_saved", lang=user_lang,
                        filename=filename, size=size_formatted)
            )

        logger.info(f"Manual backup created by admin: {filename}")

    except Exception as e:
        logger.error(f"Backup command failed: {e}", exc_info=True)
        await update.message.reply_text(
            get_text("admin.backup_failed", lang=user_lang, error=str(e))
        )


# Main commands handler (for compatibility)
async def commands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle commands"""
    pass
