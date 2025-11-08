#!/usr/bin/env python3
"""
Telegram Support Bot - Main Entry Point
Support system for users via Telegram bot
"""
import asyncio
import logging
import os
from telegram.ext import ApplicationBuilder
from telegram import Update

from config import (
    TOKEN, ADMIN_ID, BOT_API_BASE, REQUEST_TIMEOUT,
    post_init, post_shutdown, AUTO_CLOSE_AFTER_HOURS
)
from locales import load_locales, set_locale
from handlers import register_all_handlers

logger = logging.getLogger(__name__)

# Application instance (global)
application = None


async def cleanup_logs_async():
    """Wrapper for sync cleanup_old_logs function"""
    from services.logs import log_service
    log_service.cleanup_old_logs()


async def backup_async():
    """Wrapper for sync create_backup function"""
    from services.backup import backup_service
    backup_service.create_backup()


async def run_bot():
    """Start bot with polling"""
    global application

    try:
        async with application:
            await application.start()

            # Configure bot menu
            logger.info("Setting up bot menu...")
            try:
                from utils.menu import setup_bot_menu
                await setup_bot_menu(application)
                logger.info("Bot menu configured successfully")
            except Exception as e:
                logger.error(f"Failed to setup bot menu: {e}", exc_info=True)

            # Initialize and start scheduler
            logger.info("Starting scheduler service...")
            try:
                from services.scheduler import scheduler_service
                from services.ticket_auto_close import auto_close_inactive_tickets

                # Start scheduler
                await scheduler_service.start()
                logger.info("Scheduler service started")

                # Add periodic jobs with async wrappers
                await scheduler_service.add_job(
                    "cleanup_logs",
                    cleanup_logs_async,
                    3600  # 1 hour in seconds
                )
                logger.info("Added job: cleanup_logs (3600s)")

                await scheduler_service.add_job(
                    "daily_backup",
                    backup_async,
                    86400  # 24 hours in seconds
                )
                logger.info("Added job: daily_backup (86400s)")

                # Add auto-close tickets job
                await scheduler_service.add_job(
                    "auto_close_tickets",
                    auto_close_inactive_tickets,
                    3600  # Check every hour
                )
                logger.info(
                    f"Added job: auto_close_tickets "
                    f"(check interval: 3600s, timeout: {AUTO_CLOSE_AFTER_HOURS}h)"
                )

            except Exception as e:
                logger.error(f"Failed to setup scheduler: {e}", exc_info=True)

            # Remove shutdown flag
            shutdown_flag = os.path.join(os.path.dirname(__file__), ".shutdown")
            try:
                if os.path.exists(shutdown_flag):
                    os.remove(shutdown_flag)
                    logger.debug("Shutdown flag removed")
            except OSError as e:
                logger.warning(f"Could not remove shutdown flag: {e}")

            # Configure alert service
            try:
                from services.alerts import alert_service
                alert_service.set_bot(application.bot)
                logger.info("Alert service bot configured")

                # Send startup alert
                await alert_service.send_startup_alert()
                logger.info("Startup alert sent successfully")
            except Exception as e:
                logger.error(f"Failed to setup alerts: {e}", exc_info=True)

            logger.info("Bot is running...")
            from locales import get_text
            print(get_text("alerts.bot_started"))

            # Start polling
            await application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )

            # Wait for shutdown signal
            stop_event = asyncio.Event()

            # Add signal handlers
            loop = asyncio.get_running_loop()

            def signal_handler(sig):
                """Sync signal handler for loop signals"""
                asyncio.create_task(shutdown_handler(sig, stop_event))

            loop.add_signal_handler(2, signal_handler, 2)   # SIGINT
            loop.add_signal_handler(15, signal_handler, 15)  # SIGTERM

            # Wait for stop event
            await stop_event.wait()
            logger.info("Stop event received, shutting down...")

            # Stop polling
            await application.updater.stop()
            logger.info("Polling stopped")

    except Exception as e:
        logger.critical(f"Fatal error in run_bot: {e}", exc_info=True)
        raise
    finally:
        try:
            # Stop scheduler before stopping application
            try:
                from services.scheduler import scheduler_service
                await scheduler_service.stop()
                logger.info("Scheduler service stopped")
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}", exc_info=True)

            await application.stop()
            logger.info("Application stopped")
        except Exception as e:
            logger.error(f"Error stopping application: {e}", exc_info=True)


async def shutdown_handler(sig, stop_event):
    """Handle shutdown signal"""
    logger.info(f"Received signal {sig}, stopping bot...")

    # Stop scheduler
    try:
        from services.scheduler import scheduler_service
        await scheduler_service.stop()
        logger.info("Scheduler stopped during shutdown")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}", exc_info=True)

    # Send shutdown alert
    try:
        from services.alerts import alert_service
        await alert_service.send_shutdown_alert()
        logger.info("Shutdown alert sent")
    except Exception as e:
        logger.error(f"Failed to send shutdown alert: {e}", exc_info=True)

    # Save data
    try:
        from storage.data_manager import data_manager
        data_manager.save()
        logger.info("Data saved")
    except Exception as e:
        logger.error(f"Failed to save data: {e}", exc_info=True)

    # Set stop event
    stop_event.set()


async def cleanup():
    """Clean up resources"""
    shutdown_flag = os.path.join(os.path.dirname(__file__), ".shutdown")
    try:
        with open(shutdown_flag, "w") as f:
            f.write("shutdown")
        logger.info("Shutdown flag created")
    except OSError as e:
        logger.warning(f"Could not create shutdown flag: {e}")


def main():
    """Main entry point"""
    global application

    # Load locales
    load_locales()
    from config import DEFAULT_LOCALE
    set_locale(DEFAULT_LOCALE)

    # Build application
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .base_url(BOT_API_BASE + "/bot")
        .connect_timeout(REQUEST_TIMEOUT)
        .read_timeout(REQUEST_TIMEOUT)
        .write_timeout(REQUEST_TIMEOUT)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register handlers
    register_all_handlers(application)

    # Run bot
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
    finally:
        try:
            asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)


if __name__ == "__main__":
    main()
