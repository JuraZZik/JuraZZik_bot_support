import logging
import os
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    ADMIN_ID,
    BACKUP_ENABLED,
    BACKUP_FULL_PROJECT,
    BACKUP_FILE_LIST,
    BACKUP_SEND_TO_TELEGRAM,
    BACKUP_MAX_SIZE_MB,
    DEFAULT_LOCALE,
    RATING_ENABLED,
    ASK_MIN_LENGTH,
)
from locales import get_text
from utils.locale_helper import get_user_language, get_admin_language, set_user_language
from services.tickets import ticket_service
from services.bans import ban_manager
from services.feedback import feedback_service
from services.alerts import alert_service
from storage.data_manager import data_manager
from storage.instruction_store import ADMIN_SCREEN_MESSAGES, INSTRUCTION_MESSAGES
from utils.keyboards import (
    get_rating_keyboard,
    get_settings_keyboard,
    get_language_keyboard,
    get_user_language_keyboard,
)
from utils.admin_screen import show_admin_screen
from utils.states import (
    STATE_AWAITING_QUESTION,
    STATE_AWAITING_SUGGESTION,
    STATE_AWAITING_REVIEW,
    STATE_AWAITING_REPLY,
    STATE_SEARCH_TICKET_INPUT,
    STATE_AWAITING_BAN_USER_ID,
    STATE_AWAITING_UNBAN_USER_ID,
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main callback query handler - routes all button presses."""
    query = update.callback_query
    data = query.data
    user = update.effective_user
    user_lang = get_user_language(user.id)

    try:
        await query.answer()
    except Exception as e:
        logger.warning("Failed to answer callback query: %s", e)

    # Route to ticket view
    if data.startswith("ticket:"):
        ticket_id = data.split(":")[1]
        from handlers.admin import show_ticket_card

        await show_ticket_card(update, context, ticket_id)
        return

    # User can submit suggestion after rating
    if data == "after_rate_suggestion":
        context.user_data["state"] = STATE_AWAITING_SUGGESTION
        context.user_data["skip_cooldown"] = True
        await query.message.reply_text(
            get_text("messages.write_suggestion", lang=user_lang)
        )
        return

    # User can submit review after rating
    elif data == "after_rate_review":
        context.user_data["state"] = STATE_AWAITING_REVIEW
        context.user_data["skip_cooldown"] = True
        await query.message.reply_text(
            get_text("messages.write_review", lang=user_lang)
        )
        return

    # Delete feedback prompt message
    elif data == "cancel_feedback_prompt":
        try:
            await query.delete_message()
        except Exception as e:
            logger.error("Failed to delete feedback prompt: %s", e)
        return

    # Start question creation flow
    elif data == "user_start_question":
        await query.message.reply_text(
            get_text(
                "messages.describe_question",
                lang=user_lang,
                n=ASK_MIN_LENGTH,
            )
        )
        context.user_data["state"] = STATE_AWAITING_QUESTION
        return

    # Start suggestion submission
    elif data == "user_suggestion":
        can_send, error_msg = feedback_service.check_cooldown(
            user.id, "suggestion", user_lang
        )
        if not can_send:
            context.user_data["state"] = None
            await query.message.reply_text(error_msg)
            return

        context.user_data["state"] = STATE_AWAITING_SUGGESTION
        await query.message.reply_text(
            get_text("messages.write_suggestion", lang=user_lang)
        )
        return

    # Start review submission
    elif data == "user_review":
        can_send, error_msg = feedback_service.check_cooldown(
            user.id, "review", user_lang
        )
        if not can_send:
            context.user_data["state"] = None
            await query.message.reply_text(error_msg)
            return

        context.user_data["state"] = STATE_AWAITING_REVIEW
        await query.message.reply_text(
            get_text("messages.write_review", lang=user_lang)
        )
        return

    # Show language selection menu for user
    elif data == "user_change_language":
        keyboard = get_user_language_keyboard(user_lang)

        await query.edit_message_text(
            get_text("messages.choose_language", lang=user_lang),
            reply_markup=keyboard,
        )
        return

    # Set user language and return to menu
    elif data.startswith("user_lang:"):
        locale = data.split(":")[1]

        set_user_language(user.id, locale)

        await query.edit_message_text(
            get_text("admin.language_changed", lang=locale)
        )

        from handlers.start import get_user_inline_menu

        await context.bot.send_message(
            chat_id=user.id,
            text=get_text(
                "welcome.user",
                lang=locale,
                name=user.first_name or "friend",
            ),
            reply_markup=get_user_inline_menu(locale),
        )
        return

    # Start ticket search
    elif data == "search_ticket_start":
        if update.callback_query and update.callback_query.message:
            current_msg_id = update.callback_query.message.message_id

            try:
                await context.bot.edit_message_text(
                    chat_id=ADMIN_ID,
                    message_id=current_msg_id,
                    text=get_text("search.prompt", lang=user_lang),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text=get_text(
                                        "search.button_cancel",
                                        lang=user_lang,
                                    ),
                                    callback_data="admin_inbox",
                                )
                            ]
                        ]
                    ),
                    parse_mode="HTML",
                )
                logger.info(
                    "Updated search menu via edit: %s", current_msg_id
                )
                context.user_data["search_menu_msg_id"] = current_msg_id
                context.user_data["state"] = STATE_SEARCH_TICKET_INPUT
                return
            except Exception as e:
                error_msg = str(e)
                if "Message is not modified" not in error_msg:
                    logger.warning("Failed to edit search menu: %s", e)
                else:
                    context.user_data["search_menu_msg_id"] = current_msg_id
                    context.user_data["state"] = STATE_SEARCH_TICKET_INPUT
                    return

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=get_text("search.prompt", lang=user_lang),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=get_text(
                                "search.button_cancel", lang=user_lang
                            ),
                            callback_data="admin_inbox",
                        )
                    ]
                ]
            ),
        )
        context.user_data["search_menu_msg_id"] = msg.message_id
        context.user_data["state"] = STATE_SEARCH_TICKET_INPUT
        logger.info("New search menu created: %s", msg.message_id)
        return

    # Show admin inbox
    elif data == "admin_inbox":
        await handle_admin_inbox(update, context)
        return

    # Show admin statistics
    elif data == "admin_stats":
        await handle_admin_stats(update, context)
        return

    # Show admin settings
    elif data == "admin_settings":
        await handle_admin_settings(update, context)
        return

    # Show admin help (instructions + donate)
    elif data == "admin_help":
        from handlers.admin import admin_help_handler

        await admin_help_handler(update, context)
        return

    # Start ban user flow
    elif data == "ban_user":
        context.user_data["state"] = STATE_AWAITING_BAN_USER_ID
        await show_admin_screen(
            update,
            context,
            get_text("admin.enter_user_id", lang=user_lang),
            None,
            screen_type="settings",
        )
        return

    # Start unban user flow
    elif data == "unban_user":
        context.user_data["state"] = STATE_AWAITING_UNBAN_USER_ID
        await show_admin_screen(
            update,
            context,
            get_text("admin.enter_unban_id", lang=user_lang),
            None,
            screen_type="settings",
        )
        return

    # Show banned users list
    elif data == "bans_list":
        await handle_bans_list(update, context)
        return

    # Clear all active tickets
    elif data == "clear_tickets":
        count = ticket_service.clear_active_tickets()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        get_text("buttons.back", lang=user_lang),
                        callback_data="settings",
                    )
                ]
            ]
        )
        await show_admin_screen(
            update,
            context,
            get_text("admin.tickets_cleared", lang=user_lang)
            if count > 0
            else get_text("admin.no_active_tickets", lang=user_lang),
            keyboard,
            screen_type="settings",
        )
        return

    # Create manual backup
    elif data == "create_backup":
        from services.backup import backup_service

        admin_lang = get_admin_language()

        if not BACKUP_ENABLED:
            await show_admin_screen(
                update,
                context,
                get_text("messages.backup_disabled_full", lang=admin_lang),
                get_settings_keyboard(admin_lang),
                screen_type="settings",
            )
            return

        try:
            await query.answer(
                get_text("messages.backup_creating", lang=admin_lang),
                show_alert=False,
            )
        except Exception as e:
            logger.warning(
                "Failed to show backup creating notification: %s", e
            )

        try:
            backup_path, backup_info = backup_service.create_backup()

            if not backup_path:
                raise RuntimeError("Backup path is empty")

            backup_filename = os.path.basename(backup_path)
            size_formatted = backup_info.get(
                "size_formatted",
                f"{backup_info.get('size_mb', 0):.1f}MB",
            )

            logger.info(
                "Manual backup created: %s (%s)",
                backup_filename,
                size_formatted,
            )

            if backup_info.get("type") == "full":
                message_text = (
                    f"{get_text('admin.backup_created_sent', lang=admin_lang).format(filename=backup_filename, size=size_formatted)}\n\n"
                    f"{get_text('admin.backup_directory', lang=admin_lang)}: {backup_info.get('source_dir')}\n"
                    f"{get_text('admin.backup_excluded', lang=admin_lang)}: {backup_info.get('excluded_patterns')}\n"
                    f"{get_text('admin.backup_files', lang=admin_lang)}: {backup_info.get('files_in_archive')}\n"
                    f"{get_text('admin.backup_size', lang=admin_lang)}: {size_formatted}\n"
                    f"{get_text('admin.backup_file', lang=admin_lang)}: {backup_filename}"
                )
            else:
                message_text = (
                    f"{get_text('admin.backup_created_saved', lang=admin_lang).format(filename=backup_filename, size=size_formatted)}\n\n"
                    f"{get_text('admin.backup_files_selected', lang=admin_lang)}: {backup_info.get('files')}\n"
                    f"{get_text('admin.backup_in_archive', lang=admin_lang)}: {backup_info.get('files_in_archive')}\n"
                    f"{get_text('admin.backup_size', lang=admin_lang)}: {size_formatted}\n"
                    f"{get_text('admin.backup_file', lang=admin_lang)}: {backup_filename}"
                )

            if BACKUP_SEND_TO_TELEGRAM:
                size_mb = backup_info.get("size_mb", 0)
                if size_mb <= BACKUP_MAX_SIZE_MB:
                    caption = message_text
                    await alert_service.send_backup_file(
                        backup_path, caption
                    )
                    logger.info(
                        "Backup sent to Telegram: %s (%s)",
                        backup_filename,
                        size_formatted,
                    )
                else:
                    warning_msg = (
                        f"{get_text('admin.backup_too_large', lang=admin_lang)}\n\n"
                        f"{message_text}\n\n"
                        f"{get_text('admin.backup_size_info', lang=admin_lang)}: {size_formatted}\n"
                        f"{get_text('admin.backup_limit', lang=admin_lang)}: {BACKUP_MAX_SIZE_MB}MB\n"
                        f"{get_text('admin.backup_saved_server', lang=admin_lang)}: /bot_data/backups/{backup_filename}\n\n"
                        f"{get_text('admin.backup_available', lang=admin_lang)}"
                    )
                    message_text = warning_msg
                    logger.warning(
                        "Backup too large to send to Telegram: %s (%s > %sMB)",
                        backup_filename,
                        size_formatted,
                        BACKUP_MAX_SIZE_MB,
                    )

            await show_admin_screen(
                update,
                context,
                message_text,
                get_settings_keyboard(admin_lang),
                screen_type="settings",
            )

        except Exception as e:
            logger.error("Manual backup failed: %s", e, exc_info=True)
            admin_lang = get_admin_language()
            await show_admin_screen(
                update,
                context,
                get_text(
                    "admin.backup_failed",
                    lang=admin_lang,
                    error=str(e),
                ),
                get_settings_keyboard(admin_lang),
                screen_type="settings",
            )
        return

    # Show language selection menu for admin
    elif data == "change_language":
        await show_admin_screen(
            update,
            context,
            get_text("admin.choose_language", lang=user_lang),
            get_language_keyboard(user_lang),
            screen_type="settings",
        )
        return

    # Show admin settings menu
    elif data == "settings":
        await show_admin_screen(
            update,
            context,
            get_text("admin.settings", lang=user_lang),
            get_settings_keyboard(user_lang),
            screen_type="settings",
        )
        return

    # Set admin language
    elif data.startswith("lang:"):
        locale = data.split(":")[1]

        set_user_language(ADMIN_ID, locale)

        await show_admin_screen(
            update,
            context,
            get_text("admin.language_changed", lang=locale),
            get_settings_keyboard(locale),
            screen_type="settings",
        )
        return

    # Admin info screen
    elif data == "admin_info":
        await handle_admin_info(update, context)
        return

    # Admin debug screen
    elif data == "admin_debug":
        await handle_admin_debug(update, context)
        return

    # Handle ticket rating
    elif data.startswith("rate:"):
        if RATING_ENABLED:
            await handle_rating(update, context, data)
        else:
            await update.callback_query.answer(
                "Rating feature is disabled", show_alert=True
            )
        return

    # Handle thank you for feedback
    elif data.startswith("thank:"):
        await handle_thank_feedback(update, context, data)
        return

    # Handle admin taking ticket
    elif data.startswith("take:"):
        await handle_take_ticket(update, context, data)
        return

    # Handle ticket closing
    elif data.startswith("close:"):
        await handle_close_ticket(update, context, data)
        return

    # Handle admin reply to ticket
    elif data.startswith("reply:"):
        await handle_reply_ticket(update, context, data)
        return

    # Handle inbox filtering
    elif data.startswith("inbox_filter:"):
        await handle_inbox_filter(update, context, data)
        return

    # Handle inbox pagination
    elif data.startswith("inbox_page:"):
        await handle_inbox_page(update, context, data)
        return

    # Return to admin home menu
    elif data == "admin_home":
        admin_lang = get_admin_language()

        if update.callback_query and update.callback_query.message:
            try:
                from handlers.start import get_admin_inline_menu

                await context.bot.edit_message_text(
                    chat_id=user.id,
                    message_id=update.callback_query.message.message_id,
                    text=get_text("admin.welcome", lang=admin_lang),
                    reply_markup=get_admin_inline_menu(admin_lang),
                    parse_mode="HTML",
                )
                logger.info(
                    "Updated admin home menu: %s",
                    update.callback_query.message.message_id,
                )
                return
            except Exception as e:
                error_msg = str(e)
                if "Message is not modified" not in error_msg:
                    logger.warning("Failed to edit admin home: %s", e)
                else:
                    return

        from handlers.start import get_admin_inline_menu

        await show_admin_screen(
            update,
            context,
            get_text("admin.welcome", lang=admin_lang),
            get_admin_inline_menu(admin_lang),
            screen_type="home",
        )
        return

    # Return to user home menu
    elif data == "user_home":
        from handlers.start import get_user_inline_menu

        await query.message.reply_text(
            get_text(
                "welcome.user",
                lang=user_lang,
                name=query.from_user.first_name or "friend",
            ),
            reply_markup=get_user_inline_menu(user_lang),
        )
        return

    # No operation - used for disabled buttons
    elif data == "noop":
        return


async def handle_admin_inbox(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display incoming tickets for admin."""
    from handlers.admin import show_inbox

    await show_inbox(update, context)


async def handle_admin_stats(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display statistics for admin."""
    admin_lang = get_admin_language()

    stats = data_manager.get_stats()
    banned_count = len(ban_manager.get_banned_list())
    stats["banned_count"] = banned_count

    text = get_text("admin.stats_text", lang=admin_lang, **stats)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.main_menu", lang=admin_lang),
                    callback_data="admin_home",
                )
            ]
        ]
    )

    await show_admin_screen(update, context, text, keyboard, screen_type="stats")


async def handle_admin_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display settings menu."""
    user = update.effective_user
    admin_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    await show_admin_screen(
        update,
        context,
        get_text("admin.settings", lang=admin_lang),
        get_settings_keyboard(admin_lang),
        screen_type="settings",
    )


async def handle_bans_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display list of banned users."""
    admin_lang = get_admin_language()
    banned_users = ban_manager.get_banned_list()

    if not banned_users:
        text = get_text("admin.no_banned_users", lang=admin_lang)
    else:
        text = get_text("admin.banned_users_list", lang=admin_lang) + "\n\n"
        for user_id, reason in banned_users:
            text += f"🚫 ID: <code>{user_id}</code>\n"
            if reason:
                text += f"   Reason: {reason}\n"
            text += "\n"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.back", lang=admin_lang),
                    callback_data="settings",
                )
            ]
        ]
    )

    await show_admin_screen(update, context, text, keyboard, screen_type="settings")


async def handle_admin_info(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show bot info for admin."""
    admin_lang = get_admin_language()
    stats = data_manager.get_stats()

    from config import (
        BOT_NAME,
        BOT_VERSION,
        BOT_BUILD_DATE,
        TIMEZONE_STR,
        DEFAULT_LOCALE,
        BACKUP_ENABLED,
        BACKUP_SEND_TO_TELEGRAM,
        RATING_ENABLED,
        FEEDBACK_COOLDOWN_ENABLED,
    )

    text = get_text(
        "admin.info_text",
        lang=admin_lang,
        bot_name=BOT_NAME,
        version=BOT_VERSION,
        build_date=BOT_BUILD_DATE,
        timezone=TIMEZONE_STR,
        default_locale=DEFAULT_LOCALE,
        backup_enabled="✅" if BACKUP_ENABLED else "❌",
        backup_telegram="✅" if BACKUP_SEND_TO_TELEGRAM else "❌",
        rating_enabled="✅" if RATING_ENABLED else "❌",
        feedback_cooldown="✅" if FEEDBACK_COOLDOWN_ENABLED else "❌",
        total_users=stats["total_users"],
        total_tickets=stats["total_tickets"],
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.back", lang=admin_lang),
                    callback_data="settings",
                )
            ]
        ]
    )

    await show_admin_screen(update, context, text, keyboard, screen_type="settings")


async def handle_admin_debug(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show debug/config info for admin."""
    admin_lang = get_admin_language()

    from config import (
        DATA_DIR,
        BACKUP_DIR,
        LOG_FILE,
        LOG_LEVEL,
        STORAGE_BACKUP_INTERVAL_HOURS,
        AUTO_CLOSE_AFTER_HOURS,
    )

    text = get_text(
        "admin.debug_text",
        lang=admin_lang,
        data_dir=DATA_DIR,
        backup_dir=BACKUP_DIR,
        log_file=LOG_FILE,
        log_level=LOG_LEVEL,
        backup_interval_hours=STORAGE_BACKUP_INTERVAL_HOURS,
        auto_close_hours=AUTO_CLOSE_AFTER_HOURS,
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.back", lang=admin_lang),
                    callback_data="settings",
                )
            ]
        ]
    )

    await show_admin_screen(update, context, text, keyboard, screen_type="settings")


async def handle_rating(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle ticket rating from user with clickable ticket ID and username/id in alert."""
    parts = data.split(":")
    ticket_id = parts[1]
    rating = int(parts[2])

    user = update.effective_user
    user_lang = get_user_language(user.id)

    ticket = ticket_service.get_ticket(ticket_id)
    if not ticket:
        await update.callback_query.answer(
            get_text("errors.ticket_not_found", lang=user_lang),
            show_alert=True,
        )
        return

    ticket_service.rate_ticket(ticket_id, rating)
    logger.info("User %s rated ticket %s: %s/5", user.id, ticket_id, rating)

    await update.callback_query.edit_message_text(
        get_text("messages.thanks_for_rating", lang=user_lang),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        get_text("buttons.write_suggestion", lang=user_lang),
                        callback_data="after_rate_suggestion",
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text("buttons.write_review", lang=user_lang),
                        callback_data="after_rate_review",
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text("buttons.cancel", lang=user_lang),
                        callback_data="cancel_feedback_prompt",
                    )
                ],
            ]
        ),
    )

    username = f"@{user.username}" if user.username else "unknown"
    admin_lang = get_admin_language()
    alert_text = get_text(
        "admin.user_rated_ticket",
        lang=admin_lang,
        user_id=user.id,
        ticket_id=ticket_id,
        rating=rating,
        username=username,
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"📋 {ticket_id}", callback_data=f"ticket:{ticket_id}"
                )
            ]
        ]
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=alert_text, reply_markup=keyboard
        )
        logger.info(
            "Rating alert sent to admin %s: %s rated %s/5 by user %s",
            ADMIN_ID,
            ticket_id,
            rating,
            user.id,
        )
    except Exception as e:
        logger.error("Failed to send rating alert to admin: %s", e)


async def handle_thank_feedback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle thanking user for feedback - with button state change and type-specific message."""
    feedback_id = data.split(":")[1]
    admin_lang = get_admin_language()

    feedback = feedback_service.get_feedback(feedback_id)
    if not feedback:
        await update.callback_query.answer(
            get_text("errors.feedback_not_found", lang=admin_lang),
            show_alert=True,
        )
        return

    user_id = feedback.get("user_id")
    feedback_type = feedback.get("type")
    user_lang = get_user_language(user_id)
    message_id = feedback.get("message_id")

    feedback_service.thank_feedback(feedback_id)

    try:
        if feedback_type == "suggestion":
            thank_message = get_text(
                "messages.thanks_suggestion", lang=user_lang
            )
        elif feedback_type == "review":
            thank_message = get_text("messages.thanks_review", lang=user_lang)
        else:
            thank_message = get_text(
                "messages.admin_thanked_feedback", lang=user_lang
            )

        await context.bot.send_message(chat_id=user_id, text=thank_message)
        logger.info(
            "Thank you message sent to user %s for %s", user_id, feedback_type
        )

        if message_id:
            try:
                inactive_keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                get_text("admin.thanked", lang=admin_lang),
                                callback_data="noop",
                            )
                        ]
                    ]
                )

                await context.bot.edit_message_reply_markup(
                    chat_id=ADMIN_ID,
                    message_id=message_id,
                    reply_markup=inactive_keyboard,
                )
                logger.info(
                    "Feedback button updated to disabled: %s", feedback_id
                )
            except Exception as e:
                logger.warning("Failed to update button: %s", e)

        await update.callback_query.answer(
            get_text("admin.thank_sent", lang=admin_lang), show_alert=False
        )
        logger.info(
            "Admin thanked user %s for %s %s",
            user_id,
            feedback_type,
            feedback_id,
        )
    except Exception as e:
        logger.error("Failed to send thank message: %s", e)
        await update.callback_query.answer(
            get_text("errors.failed_to_send", lang=admin_lang),
            show_alert=True,
        )


async def handle_take_ticket(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle admin taking a ticket."""
    ticket_id = data.split(":")[1]
    admin_lang = get_admin_language()

    ticket = ticket_service.get_ticket(ticket_id)
    if not ticket:
        await update.callback_query.answer(
            get_text("errors.ticket_not_found", lang=admin_lang),
            show_alert=True,
        )
        return

    admin_id = update.effective_user.id

    ticket_service.take_ticket(ticket_id, admin_id)
    logger.info("Admin %s took ticket %s", admin_id, ticket_id)

    from handlers.admin import show_ticket_card

    await show_ticket_card(update, context, ticket_id)


async def handle_close_ticket(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle closing a ticket."""
    ticket_id = data.split(":")[1]
    admin_lang = get_admin_language()

    ticket = ticket_service.get_ticket(ticket_id)
    if not ticket:
        await update.callback_query.answer(
            get_text("errors.ticket_not_found", lang=admin_lang),
            show_alert=True,
        )
        return

    ticket_service.close_ticket(ticket_id)
    logger.info("Ticket %s closed by admin", ticket_id)

    user_id = ticket.user_id
    user_lang = get_user_language(user_id)

    try:
        if RATING_ENABLED:
            await context.bot.send_message(
                chat_id=user_id,
                text=get_text(
                    "messages.ticket_closed_rate",
                    lang=user_lang,
                ).format(ticket_id=ticket_id),
                reply_markup=get_rating_keyboard(ticket_id, user_lang),
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=get_text(
                    "messages.ticket_closed", lang=user_lang
                ).format(ticket_id=ticket_id),
            )
    except Exception as e:
        logger.error(
            "Failed to notify user about ticket closure: %s", e
        )

    await update.callback_query.answer(
        get_text("admin.ticket_closed", lang=admin_lang), show_alert=False
    )

    from handlers.admin import show_ticket_card

    await show_ticket_card(update, context, ticket_id)


async def handle_reply_ticket(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle admin reply to ticket."""
    ticket_id = data.split(":")[1]
    admin_lang = get_admin_language()

    ticket = ticket_service.get_ticket(ticket_id)
    if not ticket:
        await update.callback_query.answer(
            get_text("errors.ticket_not_found", lang=admin_lang),
            show_alert=True,
        )
        return

    context.user_data["reply_ticket_id"] = ticket_id
    context.user_data["state"] = STATE_AWAITING_REPLY

    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        get_text("admin.enter_reply", lang=admin_lang)
    )


async def handle_inbox_filter(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle inbox filtering by ticket status."""
    filter_status = data.split(":")[1]

    context.user_data["inbox_filter"] = filter_status
    context.user_data["inbox_page"] = 0

    from handlers.admin import show_inbox

    await show_inbox(update, context, status_filter=filter_status)


async def handle_inbox_page(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    """Handle inbox pagination."""
    page = int(data.split(":")[1])

    context.user_data["inbox_page"] = page
    current_filter = context.user_data.get("inbox_filter", "all")

    from handlers.admin import show_inbox

    await show_inbox(update, context, status_filter=current_filter, page=page)
