"""
Global storage for admin instruction message IDs and screen management

This module manages message IDs for different admin screens to enable
in-place editing instead of creating new messages
"""

# ❌ FOR DELETION - old system (reuses message_id across different screens)
# Old approach caused issues with updating wrong screens
INSTRUCTION_MESSAGES = {}
SEARCH_RESULT_MESSAGES = {}
INBOX_MENU_MESSAGES = {}

# ✅ NEW SYSTEM - separate message_id for each screen type
# Ensures each screen has its own message ID for proper in-place editing
ADMIN_SCREEN_MESSAGES = {
    "home": None,        # 🏠 Admin home menu
    "inbox": None,       # 📥 Incoming tickets
    "stats": None,       # 📊 Statistics screen
    "settings": None,    # ⚙️ Settings screen
    "ticket": None,      # 🎫 Ticket card
    "search": None,      # 🔍 Search results
    "ban_list": None,    # 📋 Ban list
}

# Archive for recovery/undo functionality
LAST_ADMIN_SCREENS = {}


def reset_screen(screen_type: str):
    """
    Reset message ID for specific screen
    
    Args:
        screen_type: Type of screen (home, inbox, stats, etc.)
    """
    if screen_type in ADMIN_SCREEN_MESSAGES:
        ADMIN_SCREEN_MESSAGES[screen_type] = None


def reset_all_screens():
    """
    Reset message IDs for all admin screens
    Useful when admin logs out or session ends
    """
    for key in ADMIN_SCREEN_MESSAGES:
        ADMIN_SCREEN_MESSAGES[key] = None


def get_screen_message_id(screen_type: str):
    """
    Get message ID for specific screen type
    
    Args:
        screen_type: Type of screen (home, inbox, stats, etc.)
    
    Returns:
        Message ID (int) or None if screen has no message
    """
    return ADMIN_SCREEN_MESSAGES.get(screen_type)


def set_screen_message_id(screen_type: str, message_id: int):
    """
    Set message ID for specific screen type
    Call this after creating a new message for a screen
    
    Args:
        screen_type: Type of screen (home, inbox, stats, etc.)
        message_id: Telegram message ID to store
    """
    if screen_type in ADMIN_SCREEN_MESSAGES:
        ADMIN_SCREEN_MESSAGES[screen_type] = message_id


def get_all_screen_messages() -> dict:
    """
    Get all current screen message IDs
    
    Returns:
        Dictionary of screen_type: message_id mappings
    """
    return ADMIN_SCREEN_MESSAGES.copy()


def archive_screens():
    """
    Save current screens state to archive
    Useful before making major changes
    """
    global LAST_ADMIN_SCREENS
    LAST_ADMIN_SCREENS = ADMIN_SCREEN_MESSAGES.copy()


def restore_screens():
    """
    Restore screens from archive
    Useful for undo operations
    """
    global ADMIN_SCREEN_MESSAGES
    if LAST_ADMIN_SCREENS:
        ADMIN_SCREEN_MESSAGES = LAST_ADMIN_SCREENS.copy()
