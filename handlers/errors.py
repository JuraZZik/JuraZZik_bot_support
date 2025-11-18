import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest, RetryAfter, TimedOut, NetworkError
from config import RETRY_ATTEMPTS, RETRY_BACKOFF_SEC

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler used by PTB for all uncaught exceptions."""
    try:
        # Re-raise the original error so we can handle by type
        raise context.error
    except RetryAfter as e:
        logger.warning("RetryAfter: %ss", e.retry_after)
        await asyncio.sleep(e.retry_after)
    except TimedOut:
        logger.warning("Request timed out")
    except NetworkError as e:
        logger.error("Network error: %s", e, exc_info=True)
    except BadRequest as e:
        logger.error("Bad request: %s", e, exc_info=True)
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ An error occurred while processing the request."
                )
            except Exception:
                # Avoid raising from the error handler itself
                pass
    except Exception as e:
        # Log unexpected errors with traceback
        logger.error("Unexpected error: %s", e, exc_info=True)

        # Do NOT send alert here: TelegramErrorHandler will handle alerts.
        # Only inform the user that something went wrong.
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An unexpected error occurred. Administrator has been notified."
                )
            except Exception:
                # Avoid raising from the error handler itself
                pass


async def retry_on_error(func, *args, **kwargs):
    """Retry function execution on network-related errors with exponential backoff."""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await func(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            if attempt < RETRY_ATTEMPTS - 1:
                wait_time = RETRY_BACKOFF_SEC * (2**attempt)
                logger.warning(
                    "Attempt %d failed, retrying in %ss: %s",
                    attempt + 1,
                    wait_time,
                    e,
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error("All %d attempts failed", RETRY_ATTEMPTS, exc_info=True)
                raise
        except Exception:
            # For non-network errors just re-raise
            raise
