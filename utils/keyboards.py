from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from locales import get_text, get_user_locale
from config import DEFAULT_LOCALE


def _get_user_lang(user_id: int) -> str:
    """Get user language from locales module or config default"""
    lang = get_user_locale(user_id)
    return lang if lang else DEFAULT_LOCALE


def get_rating_keyboard(ticket_id: str, user_lang: str = None):
    """Build rating keyboard for ticket quality evaluation (callback_data with numbers)"""
    user_lang = user_lang or DEFAULT_LOCALE
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text("rating.excellent", lang=user_lang), callback_data=f"rate:{ticket_id}:5"),
            InlineKeyboardButton(get_text("rating.good", lang=user_lang), callback_data=f"rate:{ticket_id}:3"),
            InlineKeyboardButton(get_text("rating.ok", lang=user_lang), callback_data=f"rate:{ticket_id}:1")
        ]
    ])


def get_settings_keyboard(user_lang: str = None):
    """Build settings administration keyboard - NO duplicate emojis!"""
    user_lang = user_lang or DEFAULT_LOCALE
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("admin.ban_user", lang=user_lang), callback_data="ban_user")],
        [InlineKeyboardButton(get_text("admin.unban_user", lang=user_lang), callback_data="unban_user")],
        [InlineKeyboardButton(get_text("admin.bans_list", lang=user_lang), callback_data="bans_list")],
        [InlineKeyboardButton(get_text("admin.clear_tickets", lang=user_lang), callback_data="clear_tickets")],
        [InlineKeyboardButton(get_text("admin.create_backup", lang=user_lang), callback_data="create_backup")],
        [InlineKeyboardButton(get_text("admin.change_language", lang=user_lang), callback_data="change_language")],
        [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]
    ])


def get_language_keyboard(user_lang: str = None):
    """Build language selection keyboard for ADMIN - loads emoji from JSON"""
    user_lang = user_lang or DEFAULT_LOCALE

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{get_text('ui.flag_ru', lang=user_lang)} Русский", callback_data="lang:ru"),
            InlineKeyboardButton(f"{get_text('ui.flag_en', lang=user_lang)} English", callback_data="lang:en")
        ],
        [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="settings")]
    ])


def get_user_language_keyboard(user_lang: str = None):
    """Build language selection keyboard for REGULAR USER - loads emoji from JSON"""
    user_lang = user_lang or DEFAULT_LOCALE

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{get_text('ui.flag_ru', lang=user_lang)} Русский", callback_data="user_lang:ru"),
            InlineKeyboardButton(f"{get_text('ui.flag_en', lang=user_lang)} English", callback_data="user_lang:en")
        ],
        [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="user_home")]
    ])


def get_admin_main_keyboard(user_lang: str = None):
    """Build admin main menu keyboard"""
    user_lang = user_lang or DEFAULT_LOCALE
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("buttons.inbox", lang=user_lang), callback_data="admin_inbox")],
        [InlineKeyboardButton(get_text("buttons.stats", lang=user_lang), callback_data="admin_stats")],
        [InlineKeyboardButton(get_text("buttons.settings", lang=user_lang), callback_data="admin_settings")]
    ])
