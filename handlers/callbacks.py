import logging
import os
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID, BACKUP_ENABLED, BACKUP_FULL_PROJECT, BACKUP_FILE_LIST, BACKUP_SEND_TO_TELEGRAM, BACKUP_MAX_SIZE_MB, DEFAULT_LOCALE
from locales import _, get_text, get_user_locale, set_locale, set_user_locale
from services.tickets import ticket_service
from services.bans import ban_manager
from services.feedback import feedback_service
from services.alerts import alert_service
from storage.data_manager import data_manager
from storage.instruction_store import ADMIN_SCREEN_MESSAGES, INSTRUCTION_MESSAGES
from utils.keyboards import get_rating_keyboard, get_settings_keyboard, get_language_keyboard, get_user_language_keyboard
from utils.admin_screen import show_admin_screen

logger = logging.getLogger(__name__)

def _get_user_lang(user_id: int) -> str:
    """Get user language from locales module or config default"""
    lang = get_user_locale(user_id)
    if lang:
        return lang

    try:
        user_data = data_manager.get_user_data(user_id)
        lang = user_data.get("locale")
        if lang:
            set_user_locale(user_id, lang)
            return lang
    except Exception as e:
        logger.warning(f"⚠️ Failed to load user locale from data_manager: {e}")

    return DEFAULT_LOCALE

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback query handler"""
    query = update.callback_query
    data = query.data
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"⚠️ Failed to answer callback query: {e}")

    if data.startswith("ticket:"):
        ticket_id = data.split(":")[1]
        from handlers.admin import show_ticket_card
        await show_ticket_card(update, context, ticket_id)
        return

    if data == "after_rate_suggestion":
        context.user_data["state"] = "awaiting_suggestion"
        context.user_data["skip_cooldown"] = True
        await query.message.reply_text(get_text("messages.write_suggestion", lang=user_lang))
        return

    elif data == "after_rate_review":
        context.user_data["state"] = "awaiting_review"
        context.user_data["skip_cooldown"] = True
        await query.message.reply_text(get_text("messages.write_review", lang=user_lang))
        return

    elif data == "cancel_feedback_prompt":
        try:
            await query.delete_message()
        except Exception as e:
            logger.error(f"Failed to delete feedback prompt: {e}")
        return

    elif data == "user_start_question":
        await query.message.reply_text(get_text("messages.describe_question", lang=user_lang, n=20))
        context.user_data["state"] = "awaiting_question"
        return

    elif data == "user_suggestion":
        can_send, error_msg = feedback_service.check_cooldown(user.id, "suggestion")
        if not can_send:
            context.user_data["state"] = None
            await query.message.reply_text(error_msg)
            return

        context.user_data["state"] = "awaiting_suggestion"
        await query.message.reply_text(get_text("messages.write_suggestion", lang=user_lang))
        return

    elif data == "user_review":
        can_send, error_msg = feedback_service.check_cooldown(user.id, "review")
        if not can_send:
            context.user_data["state"] = None
            await query.message.reply_text(error_msg)
            return

        context.user_data["state"] = "awaiting_review"
        await query.message.reply_text(get_text("messages.write_review", lang=user_lang))
        return

    elif data == "user_change_language":
        keyboard = get_user_language_keyboard(user_lang)

        await query.edit_message_text(
            get_text("messages.choose_language", lang=user_lang),
            reply_markup=keyboard
        )
        return

    elif data.startswith("user_lang:"):
        locale = data.split(":")[1]

        data_manager.update_user_data(user.id, {"locale": locale})
        set_user_locale(user.id, locale)
        set_locale(locale)

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

    elif data == "admin_inbox":
        await handle_admin_inbox(update, context)
        return

    elif data == "admin_stats":
        await handle_admin_stats(update, context)
        return

    elif data == "admin_settings":
        await handle_admin_settings(update, context)
        return

    elif data == "ban_user":
        context.user_data["state"] = "awaiting_ban_user_id"
        await show_admin_screen(update, context, get_text("admin.enter_user_id", lang=user_lang), None)
        return

    elif data == "unban_user":
        context.user_data["state"] = "awaiting_unban_user_id"
        await show_admin_screen(update, context, get_text("admin.enter_unban_id", lang=user_lang), None)
        return

    elif data == "bans_list":
        await handle_bans_list(update, context)
        return

    elif data == "clear_tickets":
        count = ticket_service.clear_active_tickets()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{get_text('ui.back_emoji', lang=user_lang)} {get_text('buttons.back', lang=user_lang)}", callback_data="settings")]
        ])
        await show_admin_screen(
            update, context,
            get_text("admin.tickets_cleared", lang=user_lang) if count > 0 else get_text("admin.no_active_tickets", lang=user_lang),
            keyboard
        )
        return

    elif data == "create_backup":
        from services.backup import backup_service

        if not BACKUP_ENABLED:
            await show_admin_screen(
                update, context,
                get_text("messages.backup_disabled_full", lang=user_lang),
                get_settings_keyboard(user_lang)
            )
            return

        admin_data = data_manager.get_user_data(ADMIN_ID)
        admin_locale = admin_data.get("locale", DEFAULT_LOCALE)

        try:
            await query.answer(get_text("messages.backup_creating", lang=user_lang), show_alert=False)
        except Exception as e:
            logger.warning(f"⚠️ Failed to show backup creating notification: {e}")

        try:
            backup_path, backup_info = backup_service.create_backup()

            if not backup_path:
                raise RuntimeError("Backup path is empty")

            backup_filename = os.path.basename(backup_path)
            size_formatted = backup_info.get("size_formatted", f"{backup_info.get('size_mb', 0):.1f}MB")

            logger.info(f"Manual backup created: {backup_filename} ({size_formatted})")

            if backup_info.get("type") == "full":
                message_text = (
                    f"✅ **Full project backup created:**\n\n"
                    f"📂 **Directory:** {backup_info.get('source_dir')}\n"
                    f"❌ **Excluded:** {backup_info.get('excluded_patterns')}\n"
                    f"📦 **Files in archive:** {backup_info.get('files_in_archive')}\n"
                    f"💾 **Size:** {size_formatted}\n"
                    f"📝 **File:** {backup_filename}"
                )
            else:
                message_text = (
                    f"✅ **Selective backup created:**\n\n"
                    f"📋 **Files:** {backup_info.get('files')}\n"
                    f"📦 **Files in archive:** {backup_info.get('files_in_archive')}\n"
                    f"💾 **Size:** {size_formatted}\n"
                    f"📝 **File:** {backup_filename}"
                )

            if BACKUP_SEND_TO_TELEGRAM:
                size_mb = backup_info.get("size_mb", 0)
                if size_mb <= BACKUP_MAX_SIZE_MB:
                    caption = f"📦 {get_text('admin.create_backup', lang=user_lang)}\n\n{message_text}"
                    await alert_service.send_backup_file(backup_path, caption)
                    logger.info(f"Backup sent to Telegram: {backup_filename} ({size_formatted})")
                else:
                    warning_msg = (
                        f"⚠️ **Backup too large to send:**\n\n"
                        f"{message_text}\n\n"
                        f"📌 Size: {size_formatted}\n"
                        f"📈 Limit: {BACKUP_MAX_SIZE_MB}MB\n"
                        f"📁 Backup saved on server: `/bot_data/backups/{backup_filename}`\n\n"
                        f"✅ File available for download from server"
                    )
                    message_text = warning_msg
                    logger.warning(f"Backup too large to send to Telegram: {backup_filename} ({size_formatted} > {BACKUP_MAX_SIZE_MB}MB)")

            await show_admin_screen(
                update, context,
                message_text,
                get_settings_keyboard(user_lang)
            )

        except Exception as e:
            logger.error(f"Manual backup failed: {e}", exc_info=True)
            await show_admin_screen(
                update, context,
                get_text("admin.backup_failed", lang=user_lang, error=str(e)),
                get_settings_keyboard(user_lang)
            )
        return

    elif data == "change_language":
        await show_admin_screen(
            update, context,
            get_text("admin.choose_language", lang=user_lang),
            get_language_keyboard(user_lang)
        )
        return

    elif data == "settings":
        await show_admin_screen(
            update, context,
            get_text("admin.settings", lang=user_lang),
            get_settings_keyboard(user_lang)
        )
        return

    elif data.startswith("lang:"):
        locale = data.split(":")[1]
        user_lang = locale

        data_manager.update_user_data(ADMIN_ID, {"locale": locale})
        set_user_locale(ADMIN_ID, locale)
        set_locale(locale)
        await show_admin_screen(
            update, context,
            get_text("admin.language_changed", lang=locale),
            get_settings_keyboard(user_lang)
        )
        return

    elif data.startswith("rate:"):
        await handle_rating(update, context, data)
        return

    elif data.startswith("thank:"):
        await handle_thank_feedback(update, context, data)
        return

    elif data.startswith("take:"):
        await handle_take_ticket(update, context, data)
        return

    elif data.startswith("close:"):
        await handle_close_ticket(update, context, data)
        return

    elif data.startswith("reply:"):
        await handle_reply_ticket(update, context, data)
        return

    elif data.startswith("inbox_filter:"):
        await handle_inbox_filter(update, context, data)
        return

    elif data.startswith("inbox_page:"):
        await handle_inbox_page(update, context, data)
        return

    elif data == "admin_home":
        user_lang = _get_user_lang(user.id)

        if update.callback_query and update.callback_query.message:
            try:
                from handlers.start import get_admin_inline_menu
                await context.bot.edit_message_text(
                    chat_id=user.id,
                    message_id=update.callback_query.message.message_id,
                    text=get_text("admin.welcome", lang=user_lang),
                    reply_markup=get_admin_inline_menu(user_lang),
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
            get_text("admin.welcome", lang=user_lang),
            get_admin_inline_menu(user_lang)
        )
        return

    elif data == "user_home":
        from handlers.start import get_user_inline_menu
        await query.message.reply_text(
            get_text("welcome.user", lang=user_lang, name=query.from_user.first_name or "friend"),
            reply_markup=get_user_inline_menu(user_lang)
        )
        return

    elif data == "noop":
        return

async def handle_admin_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display incoming tickets for admin"""
    from handlers.admin import show_inbox
    await show_inbox(update, context)

async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display statistics for admin"""
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    stats = data_manager.get_stats()
    banned_count = len(ban_manager.get_banned_list())
    stats["banned_count"] = banned_count

    text = get_text("admin.stats_text", lang=user_lang, **stats)
    home_emoji = get_text("ui.home_emoji", lang=user_lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{home_emoji} {get_text('buttons.main_menu', lang=user_lang)}", callback_data="admin_home")]
    ])

    await show_admin_screen(update, context, text, keyboard)

async def handle_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display settings menu"""
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    if user.id != ADMIN_ID:
        return

    await show_admin_screen(
        update, context,
        get_text("admin.settings", lang=user_lang),
        get_settings_keyboard(user_lang)
    )

async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle ticket rating"""
    query = update.callback_query
    parts = data.split(":")
    ticket_id = parts[1]
    rating = parts[2]
    user = query.from_user
    user_lang = _get_user_lang(user.id)

    logger.info(f"Rating received: ticket_id={ticket_id}, rating={rating}")

    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_user_locale(user.id, user_locale)
    set_locale(user_locale)
    user_lang = user_locale

    ticket = ticket_service.rate_ticket(ticket_id, rating)

    if ticket:
        rating_text = get_text(f"rating.{rating}", lang=user_lang)

        await query.edit_message_text(
            get_text("messages.thanks_rating_text", lang=user_lang, rating=rating_text)
        )
        logger.info(f"User rated ticket {ticket_id} with {rating}")

        try:
            from handlers.user import send_or_update_ticket_card, TICKET_CARD_MESSAGES
            message_id = TICKET_CARD_MESSAGES.get(ticket_id)

            if message_id:
                await send_or_update_ticket_card(context, ticket_id, action="closed", message_id=message_id)
                logger.info(f"✅ Updated admin ticket card with rating for {ticket_id}")
        except Exception as e:
            logger.error(f"❌ Failed to update admin ticket card: {e}", exc_info=True)

        try:
            suggest_emoji = get_text("buttons.suggestion", lang=user_lang)
            review_emoji = get_text("buttons.review", lang=user_lang)
            cancel_emoji = "❌"
            home_emoji = get_text("ui.home_emoji", lang=user_lang)

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(suggest_emoji, callback_data="after_rate_suggestion"),
                    InlineKeyboardButton(review_emoji, callback_data="after_rate_review")
                ],
                [
                    InlineKeyboardButton(f"{cancel_emoji} {get_text('buttons.cancel', lang=user_lang)}", callback_data="cancel_feedback_prompt"),
                    InlineKeyboardButton(f"{home_emoji} {get_text('buttons.main_menu', lang=user_lang)}", callback_data="user_home")
                ]
            ])

            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=get_text("messages.invite_review", lang=user_lang),
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Failed to send feedback prompt: {e}")
    else:
        await query.edit_message_text(get_text("messages.ticket_not_found", lang=user_lang))

async def handle_thank_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle feedback thank you"""
    query = update.callback_query
    feedback_id = data.split(":")[1]
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    feedback = feedback_service.thank_feedback(feedback_id)

    if feedback:
        feedback_type = feedback["type"]
        user_id = feedback["user_id"]

        # ADMIN sees in their language!
        admin_data = data_manager.get_user_data(ADMIN_ID)
        admin_locale = admin_data.get("locale", DEFAULT_LOCALE)
        set_locale(admin_locale)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("admin.thanked"), callback_data="noop")]
        ])

        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
            logger.info(f"✅ Updated thank button for {feedback_id}")
        except Exception as e:
            logger.error(f"Failed to update button: {e}")

        # USER sees in their language!
        user_data = data_manager.get_user_data(user_id)
        user_locale = user_data.get("locale", DEFAULT_LOCALE)
        set_locale(user_locale)

        try:
            if feedback_type == "suggestion":
                thank_msg = _("messages.thanks_suggestion")
            else:
                thank_msg = _("messages.thanks_review")

            await context.bot.send_message(
                chat_id=user_id,
                text=thank_msg
            )
            logger.info(f"✅ Thanked user {user_id} for {feedback_type}")
        except Exception as e:
            logger.error(f"Failed to send thank message to user {user_id}: {e}")

        try:
            await query.answer("✅ User received thank you message")
        except Exception as e:
            logger.warning(f"⚠️ Failed to answer thank feedback callback: {e}")
    else:
        try:
            await query.answer("❌ Feedback not found")
        except Exception as e:
            logger.warning(f"⚠️ Failed to answer feedback not found callback: {e}")

async def handle_take_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Take ticket in progress"""
    ticket_id = data.split(":")[1]
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    ticket = ticket_service.take_ticket(ticket_id, ADMIN_ID)

    if ticket:
        try:
            await context.bot.send_message(
                chat_id=ticket.user_id,
                text=get_text("messages.ticket_taken", lang=user_lang, ticket_id=ticket_id)
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        from handlers.user import send_or_update_ticket_card, TICKET_CARD_MESSAGES
        message_id = TICKET_CARD_MESSAGES.get(ticket_id) or update.callback_query.message.message_id
        TICKET_CARD_MESSAGES[ticket_id] = message_id
        await send_or_update_ticket_card(context, ticket_id, action="working", message_id=message_id)
    else:
        await show_admin_screen(update, context, get_text("messages.ticket_not_found", lang=user_lang), None)

async def handle_close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Close ticket"""
    ticket_id = data.split(":")[1]
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    ticket = ticket_service.close_ticket(ticket_id)

    if ticket:
        from handlers.user import send_or_update_ticket_card, TICKET_CARD_MESSAGES

        message_id = TICKET_CARD_MESSAGES.get(ticket_id) or update.callback_query.message.message_id
        TICKET_CARD_MESSAGES[ticket_id] = message_id

        logger.info(f"Saved message_id={message_id} for ticket {ticket_id}")

        await send_or_update_ticket_card(context, ticket_id, action="closed", message_id=message_id)

        try:
            await context.bot.send_message(
                chat_id=ticket.user_id,
                text=get_text("messages.rate_quality", lang=user_lang),
                reply_markup=get_rating_keyboard(ticket_id, user_lang)
            )
        except Exception as e:
            logger.error(f"Failed to send rating to user {ticket.user_id}: {e}")
    else:
        await show_admin_screen(update, context, get_text("messages.ticket_not_found", lang=user_lang), None)

async def handle_reply_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Start replying to ticket"""
    ticket_id = data.split(":")[1]
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    ticket = None
    for t in data_manager.get_all_tickets():
        if t.id == ticket_id:
            ticket = t
            break

    if not ticket:
        try:
            await update.callback_query.answer("❌ Ticket not found", show_alert=True)
        except Exception as e:
            logger.warning(f"⚠️ Failed to answer callback (ticket not found): {e}")
        return

    if ticket.status != "working":
        try:
            await update.callback_query.answer(
                "⚠️ First press '✅ Take in progress'",
                show_alert=True
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to answer callback (not in working status): {e}")
        return

    context.user_data["state"] = "awaiting_reply"
    context.user_data["reply_ticket_id"] = ticket_id

    try:
        await update.callback_query.answer("✍️ Enter your reply")
    except Exception as e:
        logger.warning(f"⚠️ Failed to answer callback (reply instruction): {e}")

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=get_text("messages.enter_reply", lang=user_lang)
    )

async def handle_inbox_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Filter tickets by status"""
    filter_status = data.split(":")[1]

    context.user_data["inbox_filter"] = filter_status
    context.user_data["inbox_page"] = 0

    from handlers.admin import show_inbox
    await show_inbox(update, context)

async def handle_inbox_page(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Switch inbox page for pagination"""
    page = int(data.split(":")[1])

    context.user_data["inbox_page"] = page

    from handlers.admin import show_inbox
    await show_inbox(update, context)

async def handle_bans_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display list of banned users"""
    user = update.effective_user
    user_lang = _get_user_lang(user.id)

    banned = ban_manager.get_banned_list()

    if not banned:
        text = get_text("admin.no_bans", lang=user_lang)
    else:
        lines = ["📛 Banned users list:"]
        for user_id, reason in banned:
            lines.append(f"• ID: {user_id} - {reason}")
        text = "\n".join(lines)

    await show_admin_screen(update, context, text, get_settings_keyboard(user_lang))
