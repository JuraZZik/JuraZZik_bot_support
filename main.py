#!/usr/bin/env python3
"""
JuraZZik Support Bot
Version: 2.7.0
Build Date: 2025-11-18

Telegram Support Bot with ticket system, admin panel, and backup functionality.
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Import configuration first
from config import (
    TOKEN, ADMIN_ID,
    post_init, post_shutdown,
    BOT_NAME, BOT_VERSION, BOT_BUILD_DATE
)

# Import handlers
from handlers.start import start_handler
from handlers.user import (
    text_message_handler,
    media_handler
)
from handlers.admin import (
    home_handler
)
from handlers.commands import (
    admin_command,
    backup_command,
    test_error_command,  # NEW: import test_error_command
)
from handlers.callbacks import callback_handler
from handlers.errors import error_handler

logger = logging.getLogger(__name__)


def main():
    """Main function to run the bot"""

    # Create application
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Add command handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("backup", backup_command))

    # NEW: test command to trigger an intentional error (for error-handler verification)
    application.add_handler(CommandHandler("test_error", test_error_command))

    # Add callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL |
         filters.AUDIO | filters.VOICE | filters.Sticker.ALL |
         filters.ANIMATION | filters.VIDEO_NOTE) & ~filters.COMMAND,
        media_handler
    ))

    # Add error handler
    application.add_error_handler(error_handler)

    logger.info(f"Starting {BOT_NAME} v{BOT_VERSION} (build {BOT_BUILD_DATE})")
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info("Starting bot with run_polling()...")

    # Run bot - post_init and post_shutdown will be called automatically
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
