import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_ID, ASK_MIN_LENGTH, ENABLE_MEDIA_FROM_USERS, DEFAULT_LOCALE
from locales import get_text
from utils.locale_helper import get_user_language, get_admin_language, set_user_language
from services.tickets import ticket_service
from services.feedback import feedback_service
from services.bans import ban_manager
from storage.data_manager import data_manager
from utils.keyboards import get_rating_keyboard
from utils.formatters import format_ticket_card
from utils.states import (
    STATE_AWAITING_QUESTION,
    STATE_AWAITING_SUGGESTION,
    STATE_AWAITING_REVIEW,
    STATE_AWAITING_REPLY,
)

logger = logging.getLogger(__name__)

# Storage for ticket card message_ids for editing
TICKET_CARD_MESSAGES: dict[str, int] = {}


async def send_or_update_ticket_card(
    context: ContextTypes.DEFAULT_TYPE,
    ticket_id: str,
    action: str = "new",
    message_id: int | None = None,
) -> None:
    """Send or update ticket card to admin."""
    try:
        ticket = None
        for t in data_manager.get_all_tickets():
            if t.id == ticket_id:
                ticket = t
                break

        if not ticket:
            logger.error("Ticket %s not found", ticket_id)
            return

        admin_lang = get_admin_language()

        text = format_ticket_card(ticket)

        if action == "new":
            text = f"{get_text('notifications.new_ticket', lang=admin_lang)}\n\n{text}"
        elif action == "message":
            text = f"{get_text('notifications.new_message', lang=admin_lang)}\n\n{text}"
        elif action == "working":
            text = f"{get_text('notifications.ticket_in_progress', lang=admin_lang)}\n\n{text}"
        elif action == "closed":
            text = f"{get_text('notifications.ticket_closed', lang=admin_lang)}\n\n{text}"

        buttons: list[list[InlineKeyboardButton]] = []

        if ticket.status == "new":
            buttons.append(
                [
                    InlineKeyboardButton(
                        get_text("buttons.take", lang=admin_lang),
                        callback_data=f"take:{ticket_id}",
                    ),
                    InlineKeyboardButton(
                        get_text("buttons.close", lang=admin_lang),
                        callback_data=f"close:{ticket_id}",
                    ),
                ]
            )
        elif ticket.status == "working":
            buttons.append(
                [
                    InlineKeyboardButton(
                        get_text("buttons.reply", lang=admin_lang),
                        callback_data=f"reply:{ticket_id}",
                    ),
                    InlineKeyboardButton(
                        get_text("buttons.close", lang=admin_lang),
                        callback_data=f"close:{ticket_id}",
                    ),
                ]
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    get_text("buttons.main_menu", lang=admin_lang),
                    callback_data="admin_home",
                )
            ]
        )
        keyboard = InlineKeyboardMarkup(buttons)

        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=ADMIN_ID,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                )
                TICKET_CARD_MESSAGES[ticket_id] = message_id
                logger.info("Updated ticket card (edited): %s", ticket_id)
                return
            except Exception as e:
                logger.warning("Failed to edit ticket card, will recreate: %s", e)

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID, text=text, reply_markup=keyboard
        )
        TICKET_CARD_MESSAGES[ticket_id] = msg.message_id
        logger.info("Ticket card sent to admin: %s", ticket_id)

    except Exception as e:
        logger.error(
            "Failed to send/update ticket card: %s", e, exc_info=True
        )


async def ask_question_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start creating a question ticket."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    if ban_manager.is_banned(user.id):
        await update.message.reply_text(
            get_text("messages.banned", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    active_ticket = ticket_service.get_user_active_ticket(user.id)
    if active_ticket:
        await update.message.reply_text(
            get_text(
                "messages.ticket_in_progress",
                lang=user_lang,
                ticket_id=active_ticket.id,
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    context.user_data["state"] = STATE_AWAITING_QUESTION
    await update.message.reply_text(
        get_text(
            "messages.describe_question",
            lang=user_lang,
            n=ASK_MIN_LENGTH,
        ),
        reply_markup=ReplyKeyboardRemove(),
    )


async def suggestion_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start sending suggestion."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    if ban_manager.is_banned(user.id):
        await update.message.reply_text(
            get_text("messages.banned", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    can_send, error_msg = feedback_service.check_cooldown(
        user.id, "suggestion", user_lang
    )
    if not can_send:
        await update.message.reply_text(
            error_msg, reply_markup=ReplyKeyboardRemove()
        )
        return

    context.user_data["state"] = STATE_AWAITING_SUGGESTION
    await update.message.reply_text(
        get_text("messages.write_suggestion", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )


async def review_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Start sending review."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    if ban_manager.is_banned(user.id):
        await update.message.reply_text(
            get_text("messages.banned", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    can_send, error_msg = feedback_service.check_cooldown(
        user.id, "review", user_lang
    )
    if not can_send:
        await update.message.reply_text(
            error_msg, reply_markup=ReplyKeyboardRemove()
        )
        return

    context.user_data["state"] = STATE_AWAITING_REVIEW
    await update.message.reply_text(
        get_text("messages.write_review", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )


async def text_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle text messages from user."""
    user = update.effective_user
    text = update.message.text
    user_lang = get_user_language(user.id)

    if ban_manager.is_banned(user.id):
        await update.message.reply_text(
            get_text("messages.banned", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    state = context.user_data.get("state")

    if state == STATE_AWAITING_QUESTION:
        await handle_question_text(update, context, text)
    elif state == STATE_AWAITING_SUGGESTION:
        await handle_suggestion_text(update, context, text)
    elif state == STATE_AWAITING_REVIEW:
        await handle_review_text(update, context, text)
    elif state == STATE_AWAITING_REPLY:
        await handle_admin_reply(update, context, text)
    else:
        if user.id == ADMIN_ID:
            from handlers.admin import admin_text_handler

            await admin_text_handler(update, context)
            return

        active_ticket = ticket_service.get_user_active_ticket(user.id)
        if active_ticket:
            logger.debug(
                "Active ticket: %s, last_actor=%s, status=%s",
                active_ticket.id,
                active_ticket.last_actor,
                active_ticket.status,
            )

            if active_ticket.last_actor == "user":
                logger.warning(
                    "User %s waiting for admin reply on ticket %s",
                    user.id,
                    active_ticket.id,
                )
                await update.message.reply_text(
                    get_text(
                        "messages.wait_for_admin_reply",
                        lang=user_lang,
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                )
                return

            logger.info(
                "User %s sending message to admin on ticket %s",
                user.id,
                active_ticket.id,
            )
            await handle_ticket_message(
                update, context, active_ticket.id, text
            )
        else:
            from handlers.start import get_user_inline_menu

            await update.message.reply_text(
                get_text(
                    "messages.please_choose_from_menu", lang=user_lang
                ),
                reply_markup=get_user_inline_menu(user_lang),
            )


async def handle_question_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Handle question text from user."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    if len(text) < ASK_MIN_LENGTH:
        await update.message.reply_text(
            get_text(
                "messages.min_length",
                lang=user_lang,
                n=ASK_MIN_LENGTH,
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    ticket = ticket_service.create_ticket(
        user_id=user.id, initial_message=text, username=user.username
    )

    context.user_data["state"] = None

    await update.message.reply_text(
        get_text(
            "messages.ticket_created",
            lang=user_lang,
            ticket_id=ticket.id,
        ),
        reply_markup=ReplyKeyboardRemove(),
    )

    await send_or_update_ticket_card(context, ticket.id, action="new")


async def handle_suggestion_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Handle suggestion text from user."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    skip_cooldown = context.user_data.get("skip_cooldown", False)

    if not skip_cooldown:
        can_send, error_msg = feedback_service.check_cooldown(
            user.id, "suggestion", user_lang
        )
        if not can_send:
            await update.message.reply_text(
                error_msg, reply_markup=ReplyKeyboardRemove()
            )
            return

        feedback_service.update_last_feedback(user.id, "suggestion")

    context.user_data["state"] = None
    context.user_data["skip_cooldown"] = False

    await update.message.reply_text(
        get_text("messages.suggestion_sent", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )

    feedback_id = feedback_service.create_feedback(
        user.id, "suggestion", text
    )

    try:
        admin_lang = get_admin_language()

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        get_text(
                            "admin.thank_suggestion", lang=admin_lang
                        ),
                        callback_data=f"thank:{feedback_id}",
                    )
                ]
            ]
        )

        suggestion_header = get_text(
            "admin.suggestion_from", lang=admin_lang
        ).format(username=user.username or "unknown", user_id=user.id)

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{suggestion_header}:\n\n{text}",
            reply_markup=keyboard,
        )

        feedback_service.set_message_id(feedback_id, msg.message_id)
        logger.info("Suggestion sent to admin: %s", feedback_id)
    except Exception as e:
        logger.error(
            "Failed to send suggestion alert: %s", e, exc_info=True
        )


async def handle_review_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Handle review text from user."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    skip_cooldown = context.user_data.get("skip_cooldown", False)

    if not skip_cooldown:
        can_send, error_msg = feedback_service.check_cooldown(
            user.id, "review", user_lang
        )
        if not can_send:
            await update.message.reply_text(
                error_msg, reply_markup=ReplyKeyboardRemove()
            )
            return

        feedback_service.update_last_feedback(user.id, "review")

    context.user_data["state"] = None
    context.user_data["skip_cooldown"] = False

    await update.message.reply_text(
        get_text("messages.review_sent", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )

    feedback_id = feedback_service.create_feedback(user.id, "review", text)

    try:
        admin_lang = get_admin_language()

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        get_text("admin.thank_review", lang=admin_lang),
                        callback_data=f"thank:{feedback_id}",
                    )
                ]
            ]
        )

        review_header = get_text(
            "admin.review_from", lang=admin_lang
        ).format(username=user.username or "unknown", user_id=user.id)

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{review_header}:\n\n{text}",
            reply_markup=keyboard,
        )

        feedback_service.set_message_id(feedback_id, msg.message_id)
        logger.info("Review sent to admin: %s", feedback_id)
    except Exception as e:
        logger.error(
            "Failed to send review alert: %s", e, exc_info=True
        )


async def handle_ticket_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ticket_id: str,
    text: str,
) -> None:
    """Handle message in active ticket."""
    user = update.effective_user
    user_lang = get_user_language(user.id)

    ticket_service.add_message(ticket_id, "user", text)

    await update.message.reply_text(
        get_text("messages.message_sent", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )

    admin_lang = get_admin_language()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("search.button_open", lang=admin_lang),
                    callback_data=f"ticket:{ticket_id}",
                )
            ]
        ]
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👤 @{user.username or 'unknown'} (ID: {user.id}):\n\n{text}",
            reply_markup=keyboard,
        )
        logger.info("Message sent to admin from user %s", user.id)
    except Exception as e:
        logger.error("Failed to send message to admin: %s", e)

    message_id = TICKET_CARD_MESSAGES.get(ticket_id)
    await send_or_update_ticket_card(
        context, ticket_id, action="message", message_id=message_id
    )


async def handle_admin_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Handle admin reply to ticket."""
    ticket_id = context.user_data.get("reply_ticket_id")
    if not ticket_id:
        return

    ticket = ticket_service.add_message(
        ticket_id, "support", text, ADMIN_ID
    )

    if not ticket:
        user_lang = get_user_language(update.effective_user.id)
        await update.message.reply_text(
            get_text("messages.ticket_not_found", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    user_lang = get_user_language(ticket.user_id)

    context.user_data["state"] = None
    context.user_data["reply_ticket_id"] = None

    admin_lang = get_admin_language()

    await update.message.reply_text(
        get_text("messages.answer_sent", lang=admin_lang),
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        await context.bot.send_message(
            chat_id=ticket.user_id,
            text=f"{get_text('messages.admin_reply', lang=user_lang)}\n\n{text}",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as e:
        logger.error(
            "Failed to send message to user %s: %s", ticket.user_id, e
        )

    message_id = TICKET_CARD_MESSAGES.get(ticket_id)
    await send_or_update_ticket_card(
        context, ticket_id, action="working", message_id=message_id
    )


async def media_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle media files (photos, videos, documents, etc.)."""
    user = update.effective_user

    if ban_manager.is_banned(user.id):
        return

    if user.id != ADMIN_ID and not ENABLE_MEDIA_FROM_USERS:
        user_lang = get_user_language(user.id)
        await update.message.reply_text(
            get_text("messages.media_not_allowed", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    user_lang = get_user_language(user.id)

    if update.message.photo:
        media_type = get_text("media_types.photo", lang=user_lang)
    elif update.message.video:
        media_type = get_text("media_types.video", lang=user_lang)
    elif update.message.document:
        media_type = get_text("media_types.document", lang=user_lang)
    elif update.message.audio:
        media_type = get_text("media_types.audio", lang=user_lang)
    elif update.message.voice:
        media_type = get_text("media_types.voice", lang=user_lang)
    elif update.message.sticker:
        media_type = get_text("media_types.sticker", lang=user_lang)
    elif update.message.animation:
        media_type = get_text("media_types.animation", lang=user_lang)
    elif update.message.video_note:
        media_type = get_text("media_types.video_note", lang=user_lang)
    else:
        media_type = get_text("media_types.unknown", lang=user_lang)

    state = context.user_data.get("state")

    if state == STATE_AWAITING_REPLY:
        ticket_id = context.user_data.get("reply_ticket_id")
        if ticket_id:
            ticket = ticket_service.add_message(
                ticket_id, "support", f"[{media_type}]", ADMIN_ID
            )

            if ticket:
                context.user_data["state"] = None
                context.user_data["reply_ticket_id"] = None

                admin_lang = get_admin_language()

                await update.message.reply_text(
                    get_text("messages.answer_sent", lang=admin_lang),
                    reply_markup=ReplyKeyboardRemove(),
                )

                try:
                    await update.message.forward(chat_id=ticket.user_id)
                except Exception as e:
                    logger.error(
                        "Failed to forward media to user %s: %s",
                        ticket.user_id,
                        e,
                    )

                message_id = TICKET_CARD_MESSAGES.get(ticket_id)
                await send_or_update_ticket_card(
                    context,
                    ticket_id,
                    action="working",
                    message_id=message_id,
                )
        return

    active_ticket = ticket_service.get_user_active_ticket(user.id)
    if active_ticket:
        if active_ticket.last_actor == "user":
            await update.message.reply_text(
                get_text(
                    "messages.wait_for_admin_reply", lang=user_lang
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        ticket_service.add_message(
            active_ticket.id, "user", f"[{media_type}]"
        )

        await update.message.reply_text(
            get_text("messages.message_sent", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )

        admin_lang = get_admin_language()

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"📋 {get_text('search.button_open', lang=admin_lang)}",
                        callback_data=f"ticket:{active_ticket.id}",
                    )
                ]
            ]
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"👤 @{user.username or 'unknown'} (ID: {user.id}):\n[{media_type}]",
                reply_markup=keyboard,
            )
            logger.info(
                "Media notification sent to admin from user %s", user.id
            )
        except Exception as e:
            logger.error(
                "Failed to send media notification to admin: %s", e
            )

        message_id = TICKET_CARD_MESSAGES.get(active_ticket.id)
        await send_or_update_ticket_card(
            context,
            active_ticket.id,
            action="message",
            message_id=message_id,
        )


async def back_to_service_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Return to service menu."""
    user_lang = get_user_language(update.effective_user.id)
    context.user_data["state"] = None
    await update.message.reply_text(
        get_text("messages.return_to_menu", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )


async def support_menu_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Return to support menu."""
    user_lang = get_user_language(update.effective_user.id)
    context.user_data["state"] = None
    await update.message.reply_text(
        get_text("messages.return_to_support_menu", lang=user_lang),
        reply_markup=ReplyKeyboardRemove(),
    )
