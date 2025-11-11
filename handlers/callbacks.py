import logging
import os
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import (
    ADMIN_ID, BACKUP_ENABLED, BACKUP_FULL_PROJECT, BACKUP_FILE_LIST,
    BACKUP_SEND_TO_TELEGRAM, BACKUP_MAX_SIZE_MB, DEFAULT_LOCALE, RATING_ENABLED
)
from locales import get_text
from utils.locale_helper import get_user_language, get_admin_language, set_user_language
from services.tickets import ticket_service
from services.bans import ban_manager
from services.feedback import feedback_service
from services.alerts import alert_service
from storage.data_manager import data_manager
from storage.instruction_store import ADMIN_SCREEN_MESSAGES, INSTRUCTION_MESSAGES
from utils.keyboards import get_rating_keyboard, get_settings_keyboard, get_language_keyboard, get_user_language_keyboard
from utils.admin_screen import show_admin_screen

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback query handler - routes all button presses"""
    query = update.callback_query
    data = query.data
    user = update.effective_user
    user_lang = get_user_language(user.id)

    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"⚠️ Failed to answer callback query: {e}")

    # Route to ticket view
    if data.startswith("ticket:"):
        ticket_id = data.split(":")[1]
        from handlers.admin import show_ticket_card
        await show_ticket_card(update, context, ticket_id)
        return

    # After rating, user can submit suggestion
    if data == "after_rate_suggestion":
        context.user_data["state"] = "awaiting_suggestion"
        context.user_data["skip_cooldown"] = True
        await query.message.reply_text(get_text("messages.write_suggestion", lang=user_lang))
        return

    # After rating, user can submit review
    elif data == "after_rate_review":
        context.user_data["state"] = "awaiting_review"
        context.user_data["skip_cooldown"] = True
        await query.message.reply_text(get_text("messages.write_review", lang=user_lang))
        return

    # Cancel feedback prompt
    elif data == "cancel_feedback_prompt":
        try:
            await query.delete_message()
        except Exception as e:
            logger.error(f"Failed to delete feedback prompt: {e}")
        return

    # Start asking question
    elif data == "user_start_question":
        await query.message.reply_text(get_text("messages.describe_question", lang=user_lang, n=20))
        context.user_data["state"] = "awaiting_question"
        return

    # Submit suggestion
    elif data == "user_suggestion":
        can_send, error_msg = feedback_service.check_cooldown(user.id, "suggestion", user_lang)
        if not can_send:
            context.user_data["state"] = None
            await query.message.reply_text(error_msg)
            return

        context.user_data["state"] = "awaiting_suggestion"
        await query.message.reply_text(get_text("messages.write_suggestion", lang=user_lang))
        return

    # Submit review
    elif data == "user_review":
        can_send, error_msg = feedback_service.check_cooldown(user.id, "review", user_lang)
        if not can_send:
            context.user_data["state"] = None
            await query.message.reply_text(error_msg)
            return

        context.user_data["state"] = "awaiting_review"
        await query.message.reply_text(get_text("messages.write_review", lang=user_lang))
        return

    # Change language
    elif data == "user_change_language":
        keyboard = get_user_language_keyboard(user_lang)

        await query.edit_message_text(
            get_text("messages.choose_language", lang=user_lang),
            reply_markup=keyboard
        )
        return

    # Set user language
    elif data.startswith("user_lang:"):
        locale = data.split(":")[1]

        set_user_language(user.id, locale)

        await query.edit_message_text(
            get_text("admin.language_changed", lang=locale)
        )

        from handlers.start import get_user_inline_menu
        await context.bot.send_message(
            chat_id=user.id,
            text=get_text("welcome.user", lang=locale, name=user.first_name or "friend"),
            reply_markup=get_user_inline_menu(locale)
        )
        return

    # Start search
    elif data == "search_ticket_start":
        if update.callback_query and update.callback_query.message:
            current_msg_id = update.callback_query.message.message_id

            try:
                await context.bot.edit_message_text(
                    chat_id=ADMIN_ID,
                    message_id=current_msg_id,
                    text=get_text("search.prompt", lang=user_lang),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(text=get_text("search.button_cancel", lang=user_lang), callback_data="admin_inbox")
                    ]]),
                    parse_mode='HTML'
                )
                logger.info(f"✅ Updated search menu via edit: {current_msg_id}")
                context.user_data["search_menu_msg_id"] = current_msg_id
                context.user_data["state"] = "search_ticket_input"
                return
            except Exception as e:
                error_msg = str(e)
                if "Message is not modified" not in error_msg:
                    logger.warning(f"⚠️ Failed to edit search menu: {e}")
                else:
                    context.user_data["search_menu_msg_id"] = current_msg_id
                    context.user_data["state"] = "search_ticket_input"
                    return

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=get_text("search.prompt", lang=user_lang),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(text=get_text("search.button_cancel", lang=user_lang), callback_data="admin_inbox")
            ]])
        )
        context.user_data["search_menu_msg_id"] = msg.message_id
        context.user_data["state"] = "search_ticket_input"
        logger.info(f"🔍 New search menu created: {msg.message_id}")
        return

    # Admin inbox
    elif data == "admin_inbox":
        await handle_admin_inbox(update, context)
        return

    # Admin stats
    elif data == "admin_stats":
        await handle_admin_stats(update, context)
        return

    # Admin settings
    elif data == "admin_settings":
        await handle_admin_settings(update, context)
        return

    # Ban user
    elif data == "ban_user":
        context.user_data["state"] = "awaiting_ban_user_id"
        await show_admin_screen(update, context, get_text("admin.enter_user_id", lang=user_lang), None, screen_type="settings")
        return

    # Unban user
    elif data == "unban_user":
        context.user_data["state"] = "awaiting_unban_user_id"
        await show_admin_screen(update, context, get_text("admin.enter_unban_id", lang=user_lang), None, screen_type="settings")
        return

    # View bans list
    elif data == "bans_list":
        await handle_bans_list(update, context)
        return

    # Clear active tickets
    elif data == "clear_tickets":
        count = ticket_service.clear_active_tickets()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="settings")]
        ])
        await show_admin_screen(
            update, context,
            get_text("admin.tickets_cleared", lang=user_lang) if count > 0 else get_text("admin.no_active_tickets", lang=user_lang),
            keyboard,
            screen_type="settings"
        )
        return

    # Create backup
    elif data == "create_backup":
        from services.backup import backup_service

        admin_lang = get_admin_language()

        if not BACKUP_ENABLED:
            await show_admin_screen(
                update, context,
                get_text("messages.backup_disabled_full", lang=admin_lang),
                get_settings_keyboard(admin_lang),
                screen_type="settings"
            )
            return

        try:
            await query.answer(get_text("messages.backup_creating", lang=admin_lang), show_alert=False)
        except Exception as e:
            logger.warning(f"⚠️ Failed to show backup creating notification: {e}")

        try:
            backup_path, backup_info = backup_service.create_backup()

            if not backup_path:
                raise RuntimeError("Backup path is empty")

            backup_filename = os.path.basename(backup_path)
            size_formatted = backup_info.get("size_formatted", f"{backup_info.get('size_mb', 0):.1f}MB")

            logger.info(f"Manual backup created: {backup_filename} ({size_formatted})")

            # BACKUP INFORMATION
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
                    await alert_service.send_backup_file(backup_path, caption)
                    logger.info(f"Backup sent to Telegram: {backup_filename} ({size_formatted})")
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
                    logger.warning(f"Backup too large to send to Telegram: {backup_filename} ({size_formatted} > {BACKUP_MAX_SIZE_MB}MB)")

            await show_admin_screen(
                update, context,
                message_text,
                get_settings_keyboard(admin_lang),
                screen_type="settings"
            )

        except Exception as e:
            logger.error(f"Manual backup failed: {e}", exc_info=True)
            admin_lang = get_admin_language()
            await show_admin_screen(
                update, context,
                get_text("admin.backup_failed", lang=admin_lang, error=str(e)),
                get_settings_keyboard(admin_lang),
                screen_type="settings"
            )
        return

    # Change language
    elif data == "change_language":
        await show_admin_screen(
            update, context,
            get_text("admin.choose_language", lang=user_lang),
            get_language_keyboard(user_lang),
            screen_type="settings"
        )
        return

    # Settings menu
    elif data == "settings":
        await show_admin_screen(
            update, context,
            get_text("admin.settings", lang=user_lang),
            get_settings_keyboard(user_lang),
            screen_type="settings"
        )
        return

    # Set admin language
    elif data.startswith("lang:"):
        locale = data.split(":")[1]

        set_user_language(ADMIN_ID, locale)

        await show_admin_screen(
            update, context,
            get_text("admin.language_changed", lang=locale),
            get_settings_keyboard(locale),
            screen_type="settings"
        )
        return

    # Rate ticket (with RATING_ENABLED check)
    elif data.startswith("rate:"):
        if RATING_ENABLED:
            await handle_rating(update, context, data)
        else:
            await update.callback_query.answer("Rating feature is disabled", show_alert=True)
        return

    # Thank feedback
    elif data.startswith("thank:"):
        await handle_thank_feedback(update, context, data)
        return

    # Take ticket
    elif data.startswith("take:"):
        await handle_take_ticket(update, context, data)
        return

    # Close ticket
    elif data.startswith("close:"):
        await handle_close_ticket(update, context, data)
        return

    # Reply to ticket
    elif data.startswith("reply:"):
        await handle_reply_ticket(update, context, data)
        return

    # Filter inbox by status
    elif data.startswith("inbox_filter:"):
        await handle_inbox_filter(update, context, data)
        return

    # Paginate inbox
    elif data.startswith("inbox_page:"):
        await handle_inbox_page(update, context, data)
        return

    # Admin home
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
                    parse_mode='HTML'
                )
                logger.info(f"✅ Updated admin home menu: {update.callback_query.message.message_id}")
                return
            except Exception as e:
                error_msg = str(e)
                if "Message is not modified" not in error_msg:
                    logger.warning(f"⚠️ Failed to edit admin home: {e}")
                else:
                    return

        from handlers.start import get_admin_inline_menu
        await show_admin_screen(
            update, context,
            get_text("admin.welcome", lang=admin_lang),
            get_admin_inline_menu(admin_lang),
            screen_type="home"
        )
        return

    # User home
    elif data == "user_home":
        from handlers.start import get_user_inline_menu
        await query.message.reply_text(
            get_text("welcome.user", lang=user_lang, name=query.from_user.first_name or "friend"),
            reply_markup=get_user_inline_menu(user_lang)
        )
        return

    # No operation
    elif data == "noop":
        return


async def handle_admin_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display incoming tickets for admin"""
    from handlers.admin import show_inbox
    await show_inbox(update, context)


async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display statistics for admin"""
    user = update.effective_user
    admin_lang = get_admin_language()

    stats = data_manager.get_stats()
    banned_count = len(ban_manager.get_banned_list())
    stats["banned_count"] = banned_count

    text = get_text("admin.stats_text", lang=admin_lang, **stats)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text('buttons.main_menu', lang=admin_lang), callback_data="admin_home")]
    ])

    await show_admin_screen(update, context, text, keyboard, screen_type="stats")


async def handle_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display settings menu"""
    user = update.effective_user
    admin_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    await show_admin_screen(
        update, context,
        get_text("admin.settings", lang=admin_lang),
        get_settings_keyboard(admin_lang),
        screen_type="settings"
    )
