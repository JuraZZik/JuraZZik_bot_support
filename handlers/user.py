import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_ID, ASK_MIN_LENGTH, ENABLE_MEDIA_FROM_USERS, DEFAULT_LOCALE
from locales import _, set_locale
from services.tickets import ticket_service
from services.feedback import feedback_service
from services.bans import ban_manager
from storage.data_manager import data_manager
from utils.keyboards import get_rating_keyboard
from utils.formatters import format_ticket_card

logger = logging.getLogger(__name__)

# Storage for ticket card message_ids for editing
TICKET_CARD_MESSAGES = {}


async def send_or_update_ticket_card(context: ContextTypes.DEFAULT_TYPE, ticket_id: str, action: str = "new", message_id: int = None):
    """Send or update ticket card to admin"""
    try:
        ticket = None
        for t in data_manager.get_all_tickets():
            if t.id == ticket_id:
                ticket = t
                break

        if not ticket:
            logger.error(f"Ticket {ticket_id} not found")
            return

        # ADMIN sees in their language!
        admin_data = data_manager.get_user_data(ADMIN_ID)
        admin_locale = admin_data.get("locale", DEFAULT_LOCALE)
        set_locale(admin_locale)

        text = format_ticket_card(ticket)

        if action == "new":
            text = f"🆕 {_('notifications.new_ticket')}\n\n{text}"
        elif action == "message":
            text = f"💬 {_('notifications.new_message')}\n\n{text}"
        elif action == "working":
            text = f"▶️ {_('notifications.ticket_in_progress')}\n\n{text}"
        elif action == "closed":
            text = f"✅ {_('notifications.ticket_closed')}\n\n{text}"

        buttons = []
        if ticket.status == "new":
            buttons.append([
                InlineKeyboardButton(f"▶️ {_('buttons.back')}", callback_data=f"take:{ticket_id}"),
                InlineKeyboardButton(f"✅ {_('buttons.done')}", callback_data=f"close:{ticket_id}")
            ])
        elif ticket.status == "working":
            buttons.append([InlineKeyboardButton(f"💬 {_('buttons.reply')}", callback_data=f"reply:{ticket_id}")])
            buttons.append([InlineKeyboardButton(f"✅ {_('buttons.done')}", callback_data=f"close:{ticket_id}")])

        buttons.append([InlineKeyboardButton(f"{_('ui.home_emoji')} {_('buttons.main_menu')}", callback_data="admin_home")])
        keyboard = InlineKeyboardMarkup(buttons)

        # Get saved message_id (same message)
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=ADMIN_ID,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard
                )
                TICKET_CARD_MESSAGES[ticket_id] = message_id
                logger.info(f"✅ Updated ticket card (edited): {ticket_id}")
                return
            except Exception as e:
                logger.warning(f"⚠️ Failed to edit, will recreate: {e}")

        # Create new message
        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            reply_markup=keyboard
        )
        TICKET_CARD_MESSAGES[ticket_id] = msg.message_id
        logger.info(f"✅ Ticket card sent to admin: {ticket_id}")

    except Exception as e:
        logger.error(f"Failed to send/update ticket card: {e}", exc_info=True)


async def ask_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a question ticket"""
    user = update.effective_user

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(_("messages.banned"), reply_markup=ReplyKeyboardRemove())
        return

    # Check if user has active ticket
    active_ticket = ticket_service.get_user_active_ticket(user.id)
    if active_ticket:
        await update.message.reply_text(
            _("messages.ticket_in_progress", ticket_id=active_ticket.id),
            reply_markup=ReplyKeyboardRemove()
        )
        return

    context.user_data["state"] = "awaiting_question"
    await update.message.reply_text(
        _("messages.describe_question", n=ASK_MIN_LENGTH),
        reply_markup=ReplyKeyboardRemove()
    )


async def suggestion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start sending suggestion"""
    user = update.effective_user

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(_("messages.banned"), reply_markup=ReplyKeyboardRemove())
        return

    # Check cooldown
    can_send, error_msg = feedback_service.check_cooldown(user.id, "suggestion")
    if not can_send:
        await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
        return

    context.user_data["state"] = "awaiting_suggestion"
    await update.message.reply_text(_("messages.write_suggestion"), reply_markup=ReplyKeyboardRemove())


async def review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start sending review"""
    user = update.effective_user

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(_("messages.banned"), reply_markup=ReplyKeyboardRemove())
        return

    # Check cooldown
    can_send, error_msg = feedback_service.check_cooldown(user.id, "review")
    if not can_send:
        await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
        return

    context.user_data["state"] = "awaiting_review"
    await update.message.reply_text(_("messages.write_review"), reply_markup=ReplyKeyboardRemove())


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages from user"""
    user = update.effective_user
    text = update.message.text

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(_("messages.banned"), reply_markup=ReplyKeyboardRemove())
        return

    state = context.user_data.get("state")

    if state == "awaiting_question":
        await handle_question_text(update, context, text)
    elif state == "awaiting_suggestion":
        await handle_suggestion_text(update, context, text)
    elif state == "awaiting_review":
        await handle_review_text(update, context, text)
    elif state == "awaiting_reply":
        await handle_admin_reply(update, context, text)
    else:
        # Check if user is admin
        if user.id == ADMIN_ID:
            from handlers.admin import admin_text_handler
            await admin_text_handler(update, context)
            return

        # Check if user has active ticket
        active_ticket = ticket_service.get_user_active_ticket(user.id)
        if active_ticket:
            # Check if waiting for admin reply
            if active_ticket.last_actor == "user":
                await update.message.reply_text(
                    _("messages.wait_for_admin_reply"),
                    reply_markup=ReplyKeyboardRemove()
                )
                return

            await handle_ticket_message(update, context, active_ticket.id, text)
        else:
            # Show menu if no active ticket
            from handlers.start import get_user_inline_menu
            await update.message.reply_text(
                _("messages.please_choose_from_menu"),
                reply_markup=get_user_inline_menu(user_locale)
            )


async def handle_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle question text"""
    user = update.effective_user

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    # Check minimum length
    if len(text) < ASK_MIN_LENGTH:
        await update.message.reply_text(
            _("messages.min_length", n=ASK_MIN_LENGTH),
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Create ticket
    ticket = ticket_service.create_ticket(
        user_id=user.id,
        initial_message=text,
        username=user.username
    )

    context.user_data["state"] = None

    await update.message.reply_text(
        _("messages.ticket_created", ticket_id=ticket.id),
        reply_markup=ReplyKeyboardRemove()
    )

    # Send ticket card to admin
    await send_or_update_ticket_card(context, ticket.id, action="new")


async def handle_suggestion_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle suggestion text"""
    user = update.effective_user

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    skip_cooldown = context.user_data.get("skip_cooldown", False)

    # Check cooldown if not skipped
    if not skip_cooldown:
        can_send, error_msg = feedback_service.check_cooldown(user.id, "suggestion")
        if not can_send:
            await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
            return

        feedback_service.update_last_feedback(user.id, "suggestion")

    context.user_data["state"] = None
    context.user_data["skip_cooldown"] = False

    await update.message.reply_text(_("messages.suggestion_sent"), reply_markup=ReplyKeyboardRemove())

    # Create feedback
    feedback_id = feedback_service.create_feedback(user.id, "suggestion", text)

    try:
        # ADMIN sees in their language!
        admin_data = data_manager.get_user_data(ADMIN_ID)
        admin_locale = admin_data.get("locale", DEFAULT_LOCALE)
        set_locale(admin_locale)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("admin.thank_suggestion"), callback_data=f"thank:{feedback_id}")]
        ])

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💡 {_('admin.suggestion_from', username=user.username or 'unknown', user_id=user.id)}:\n\n{text}",
            reply_markup=keyboard
        )

        feedback_service.set_message_id(feedback_id, msg.message_id)
        logger.info(f"✅ Suggestion sent to admin: {feedback_id}")
    except Exception as e:
        logger.error(f"Failed to send suggestion alert: {e}", exc_info=True)


async def handle_review_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle review text"""
    user = update.effective_user

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    skip_cooldown = context.user_data.get("skip_cooldown", False)

    # Check cooldown if not skipped
    if not skip_cooldown:
        can_send, error_msg = feedback_service.check_cooldown(user.id, "review")
        if not can_send:
            await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
            return

        feedback_service.update_last_feedback(user.id, "review")

    context.user_data["state"] = None
    context.user_data["skip_cooldown"] = False

    await update.message.reply_text(_("messages.review_sent"), reply_markup=ReplyKeyboardRemove())

    # Create feedback
    feedback_id = feedback_service.create_feedback(user.id, "review", text)

    try:
        # ADMIN sees in their language!
        admin_data = data_manager.get_user_data(ADMIN_ID)
        admin_locale = admin_data.get("locale", DEFAULT_LOCALE)
        set_locale(admin_locale)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("admin.thank_review"), callback_data=f"thank:{feedback_id}")]
        ])

        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⭐ {_('admin.review_from', username=user.username or 'unknown', user_id=user.id)}:\n\n{text}",
            reply_markup=keyboard
        )

        feedback_service.set_message_id(feedback_id, msg.message_id)
        logger.info(f"✅ Review sent to admin: {feedback_id}")
    except Exception as e:
        logger.error(f"Failed to send review alert: {e}", exc_info=True)


async def handle_ticket_message(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str, text: str):
    """Handle message in active ticket"""
    user = update.effective_user

    # Add message to ticket
    ticket_service.add_message(ticket_id, "user", text)

    await update.message.reply_text(_("messages.message_sent"), reply_markup=ReplyKeyboardRemove())

    # ADMIN sees in their language!
    admin_data = data_manager.get_user_data(ADMIN_ID)
    admin_locale = admin_data.get("locale", DEFAULT_LOCALE)
    set_locale(admin_locale)

    # BUTTON TO OPEN TICKET!
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_('search.button_open'), callback_data=f"ticket:{ticket_id}")]
    ])

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👤 @{user.username or 'unknown'} (ID: {user.id}):\n\n{text}",
            reply_markup=keyboard
        )
        logger.info(f"Message sent to admin from user {user.id}")
    except Exception as e:
        logger.error(f"Failed to send message to admin: {e}")

    # Update ticket card
    message_id = TICKET_CARD_MESSAGES.get(ticket_id)
    await send_or_update_ticket_card(context, ticket_id, action="message", message_id=message_id)


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle admin reply"""
    ticket_id = context.user_data.get("reply_ticket_id")

    if not ticket_id:
        return

    # Add reply to ticket
    ticket = ticket_service.add_message(ticket_id, "support", text, ADMIN_ID)

    if not ticket:
        await update.message.reply_text(_("messages.ticket_not_found"), reply_markup=ReplyKeyboardRemove())
        return

    # USER sees answer in their language!
    user_data = data_manager.get_user_data(ticket.user_id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    context.user_data["state"] = None
    context.user_data["reply_ticket_id"] = None

    await update.message.reply_text(_("messages.answer_sent"), reply_markup=ReplyKeyboardRemove())

    try:
        await context.bot.send_message(
            chat_id=ticket.user_id,
            text=f"{_('messages.admin_reply')}\n\n{text}",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Failed to send message to user {ticket.user_id}: {e}")

    # Update ticket card
    message_id = TICKET_CARD_MESSAGES.get(ticket_id)
    await send_or_update_ticket_card(context, ticket_id, action="working", message_id=message_id)


async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media files"""
    user = update.effective_user

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        return

    # Check if media is allowed from users
    if user.id != ADMIN_ID:
        if not ENABLE_MEDIA_FROM_USERS:
            await update.message.reply_text(_("messages.media_not_allowed"), reply_markup=ReplyKeyboardRemove())
            return

    # USER sees in their language!
    user_data = data_manager.get_user_data(user.id)
    user_locale = user_data.get("locale", DEFAULT_LOCALE)
    set_locale(user_locale)

    # Determine media type
    if update.message.photo:
        media_type = _("media_types.photo")
    elif update.message.video:
        media_type = _("media_types.video")
    elif update.message.document:
        media_type = _("media_types.document")
    elif update.message.audio:
        media_type = _("media_types.audio")
    elif update.message.voice:
        media_type = _("media_types.voice")
    elif update.message.sticker:
        media_type = _("media_types.sticker")
    elif update.message.animation:
        media_type = _("media_types.animation")
    elif update.message.video_note:
        media_type = _("media_types.video_note")
    else:
        media_type = _("media_types.unknown")

    state = context.user_data.get("state")

    # Handle admin reply with media
    if state == "awaiting_reply":
        ticket_id = context.user_data.get("reply_ticket_id")
        if ticket_id:
            ticket = ticket_service.add_message(ticket_id, "support", f"[{media_type}]", ADMIN_ID)

            if ticket:
                context.user_data["state"] = None
                context.user_data["reply_ticket_id"] = None

                await update.message.reply_text(_("messages.answer_sent"), reply_markup=ReplyKeyboardRemove())

                try:
                    await update.message.forward(chat_id=ticket.user_id)
                except Exception as e:
                    logger.error(f"Failed to forward media to user {ticket.user_id}: {e}")

                message_id = TICKET_CARD_MESSAGES.get(ticket_id)
                await send_or_update_ticket_card(context, ticket_id, action="working", message_id=message_id)
        return

    # Handle media in active ticket
    active_ticket = ticket_service.get_user_active_ticket(user.id)
    if active_ticket:
        # Check if waiting for admin reply
        if active_ticket.last_actor == "user":
            await update.message.reply_text(_("messages.wait_for_admin_reply"), reply_markup=ReplyKeyboardRemove())
            return

        # Add media to ticket
        ticket_service.add_message(active_ticket.id, "user", f"[{media_type}]")
        await update.message.reply_text(_("messages.message_sent"), reply_markup=ReplyKeyboardRemove())

        # ADMIN sees in their language!
        admin_data = data_manager.get_user_data(ADMIN_ID)
        admin_locale = admin_data.get("locale", DEFAULT_LOCALE)
        set_locale(admin_locale)

        # BUTTON TO OPEN TICKET!
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📋 {_('search.button_open')}", callback_data=f"ticket:{active_ticket.id}")]
        ])

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"👤 @{user.username or 'unknown'} (ID: {user.id}):\n[{media_type}]",
                reply_markup=keyboard
            )
            logger.info(f"Media notification sent to admin from user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send media notification to admin: {e}")

        # Update ticket card
        message_id = TICKET_CARD_MESSAGES.get(active_ticket.id)
        await send_or_update_ticket_card(context, active_ticket.id, action="message", message_id=message_id)


async def back_to_service_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Back to service handler"""
    context.user_data["state"] = None
    await update.message.reply_text(_("messages.return_to_menu"), reply_markup=ReplyKeyboardRemove())


async def support_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support menu handler"""
    context.user_data["state"] = None
    await update.message.reply_text(_("messages.return_to_support_menu"), reply_markup=ReplyKeyboardRemove())
