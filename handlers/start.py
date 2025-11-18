import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_ID, OTHER_BOT_USERNAME, DEFAULT_LOCALE
from locales import get_text, set_user_locale, set_locale
from services.bans import ban_manager
from storage.data_manager import data_manager

logger = logging.getLogger(__name__)


def get_user_inline_menu(user_lang: str | None = None) -> InlineKeyboardMarkup:
    """
    Build inline menu for regular user.

    Contains:
    - Ask question
    - Suggestion
    - Review
    - Change language
    - Back to main service bot
    """
    user_lang = user_lang or DEFAULT_LOCALE
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.ask_question", lang=user_lang),
                    callback_data="user_start_question",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.suggestion", lang=user_lang),
                    callback_data="user_suggestion",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.review", lang=user_lang),
                    callback_data="user_review",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.change_language", lang=user_lang),
                    callback_data="user_change_language",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.back_to_service", lang=user_lang),
                    url=f"https://t.me/{OTHER_BOT_USERNAME}",
                )
            ],
        ]
    )


def get_admin_inline_menu(user_lang: str | None = None) -> InlineKeyboardMarkup:
    """
    Build inline menu for admin.

    Contains:
    - Inbox
    - Statistics
    - Settings
    - Help (instructions + donate button)
    """
    user_lang = user_lang or DEFAULT_LOCALE
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.inbox", lang=user_lang),
                    callback_data="admin_inbox",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.stats", lang=user_lang),
                    callback_data="admin_stats",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.settings", lang=user_lang),
                    callback_data="admin_settings",
                )
            ],
            [
                InlineKeyboardButton(
                    get_text("buttons.admin_help", lang=user_lang),
                    callback_data="admin_help",
                )
            ],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.

    - If user is banned: show banned message.
    - Load saved user locale from data_manager.
    - For admin: show admin inline menu.
    - For regular user: show user inline menu.
    """
    user = update.effective_user

    # Check ban first
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(
            get_text("messages.banned", lang=DEFAULT_LOCALE),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Load user's saved locale (or default)
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)

    set_user_locale(user.id, user_locale)
    set_locale(user_locale)

    # Admin branch
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            get_text("admin.welcome", lang=user_locale),
            reply_markup=get_admin_inline_menu(user_locale),
        )
        logger.info("Admin %s started bot", user.id)
        return

    # Regular user branch
    await update.message.reply_text(
        get_text("welcome.user", lang=user_locale, name=user.first_name or "friend"),
        reply_markup=get_user_inline_menu(user_locale),
    )

    logger.info("User %s (@%s) started bot", user.id, user.username)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Alias wrapper for /start command (used in registration).
    """
    await start(update, context)
