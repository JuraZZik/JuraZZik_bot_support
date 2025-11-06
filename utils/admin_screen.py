import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID
from storage.instruction_store import ADMIN_SCREEN_MESSAGES

logger = logging.getLogger(__name__)


async def show_admin_screen(update, context, text, keyboard, screen_type="default"):
    """
    Display or update admin screen
    
    ALWAYS edits the SAME message (gets message_id from callback or storage)
    Creates new message only on first call
    
    Args:
        update: Telegram update object
        context: Telegram context object
        text: Message text to display
        keyboard: Reply markup (buttons)
        screen_type: Screen type identifier (home, inbox, stats, etc.)
    
    Returns:
        Message ID of updated/created message
    """

    user_id = update.effective_user.id if update.effective_user else ADMIN_ID

    # NEW LOGIC: Get message_id from callback first (if exists)
    current_msg_id = None

    # If this is callback (button pressed) - use the SAME message
    if update.callback_query and update.callback_query.message:
        current_msg_id = update.callback_query.message.message_id
        logger.info(f"🔍 Got message_id from callback: {current_msg_id}")
    else:
        # If first time from show_inbox/show_ticket - get from storage
        current_msg_id = ADMIN_SCREEN_MESSAGES.get(screen_type)
        logger.info(f"🔍 Got message_id from storage ({screen_type}): {current_msg_id}")

    if current_msg_id:
        try:
            # Edit the same message
            await context.bot.edit_message_text(
                chat_id=ADMIN_ID,
                message_id=current_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            logger.info(f"✅ Updated same message: {current_msg_id}")
            ADMIN_SCREEN_MESSAGES[screen_type] = current_msg_id
            return current_msg_id

        except Exception as e:
            error_msg = str(e)

            # If message content hasn't changed
            if "Message is not modified" in error_msg:
                logger.debug(f"ℹ️ Message not modified (same content)")
                ADMIN_SCREEN_MESSAGES[screen_type] = current_msg_id
                return current_msg_id

            # For other errors - create new message
            logger.debug(f"⚠️ Will create new message: {e}")

    # Create new message only on FIRST call
    try:
        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        ADMIN_SCREEN_MESSAGES[screen_type] = msg.message_id
        logger.info(f"✅ Created first message ({screen_type}): message_id={msg.message_id}")
        return msg.message_id

    except Exception as e:
        logger.error(f"❌ Failed to send admin screen ({screen_type}): {e}")
        return None


async def reset_admin_screen(context, screen_type: str):
    """
    Reset screen message ID when leaving that screen
    
    Clears the stored message ID so next visit creates new message
    
    Args:
        context: Telegram context object
        screen_type: Screen type identifier (home, inbox, stats, etc.)
    """
    if screen_type in ADMIN_SCREEN_MESSAGES:
        ADMIN_SCREEN_MESSAGES[screen_type] = None
        logger.info(f"🔄 Reset {screen_type} screen message ID")


async def clear_all_admin_screens(context):
    """
    Clear all admin screen message IDs
    
    Call this when:
    - Admin logs out
    - Session ends
    - Admin leaves the admin interface
    
    Args:
        context: Telegram context object
    """
    for key in ADMIN_SCREEN_MESSAGES:
        ADMIN_SCREEN_MESSAGES[key] = None
    logger.info(f"🗑 Cleared all admin screen message IDs")


async def get_current_screen_message_id(screen_type: str) -> int:
    """
    Get current message ID for screen type
    
    Args:
        screen_type: Screen type identifier
    
    Returns:
        Message ID or None if not set
    """
    return ADMIN_SCREEN_MESSAGES.get(screen_type)


async def update_screen_message_id(screen_type: str, message_id: int):
    """
    Manually update message ID for screen type
    
    Args:
        screen_type: Screen type identifier
        message_id: New message ID to store
    """
    ADMIN_SCREEN_MESSAGES[screen_type] = message_id
    logger.debug(f"📝 Updated {screen_type} message_id: {message_id}")
