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

logger = logging.getLogger(__name__)

# Storage for ticket card message_ids for editing
TICKET_CARD_MESSAGES = {}


async def send_or_update_ticket_card(context: ContextTypes.DEFAULT_TYPE, ticket_id: str, action: str = "new", message_id: int = None):
    """Send or update ticket card to admin"""
    try:
        # Find ticket by ID
        ticket = None
        for t in data_manager.get_all_tickets():
            if t.id == ticket_id:
                ticket = t
                break

        if not ticket:
            logger.error(f"Ticket {ticket_id} not found")
            return

        # Get admin language for formatting
        admin_lang = get_admin_language()

        # Format ticket card text
        text = format_ticket_card(ticket)

        # Add action header with proper localization
        if action == "new":
            text = f"{get_text('notifications.new_ticket', lang=admin_lang)}\n\n{text}"
        elif action == "message":
            text = f"{get_text('notifications.new_message', lang=admin_lang)}\n\n{text}"
        elif action == "working":
            text = f"{get_text('notifications.ticket_in_progress', lang=admin_lang)}\n\n{text}"
        elif action == "closed":
            text = f"{get_text('notifications.ticket_closed', lang=admin_lang)}\n\n{text}"

        # Initialize buttons list
        buttons = []

        # Add action buttons based on ticket status
        if ticket.status == "new":
            # Row 1: Take + Close (side by side)
            buttons.append([
                InlineKeyboardButton(get_text('buttons.take', lang=admin_lang), callback_data=f"take:{ticket_id}"),
                InlineKeyboardButton(get_text('buttons.close', lang=admin_lang), callback_data=f"close:{ticket_id}")
            ])
        elif ticket.status == "working":
            # Row 1: Reply + Close (side by side)
            buttons.append([
                InlineKeyboardButton(get_text('buttons.reply', lang=admin_lang), callback_data=f"reply:{ticket_id}"),
                InlineKeyboardButton(get_text('buttons.close', lang=admin_lang), callback_data=f"close:{ticket_id}")
            ])

        # Add main menu button (separate row)
        buttons.append([InlineKeyboardButton(get_text('buttons.main_menu', lang=admin_lang), callback_data="admin_home")])
        keyboard = InlineKeyboardMarkup(buttons)

        # Edit existing message if message_id provided
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

        # Create new message if edit failed or no message_id
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

    # Get user language
    user_lang = get_user_language(user.id)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(get_text("messages.banned", lang=user_lang), reply_markup=ReplyKeyboardRemove())
        return

    # Check if user has active ticket
    active_ticket = ticket_service.get_user_active_ticket(user.id)
    if active_ticket:
        await update.message.reply_text(
            get_text("messages.ticket_in_progress", lang=user_lang, ticket_id=active_ticket.id),
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Set state to wait for question text
    context.user_data["state"] = "awaiting_question"
    await update.message.reply_text(
        get_text("messages.describe_question", lang=user_lang, n=ASK_MIN_LENGTH),
        reply_markup=ReplyKeyboardRemove()
    )


async def suggestion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start sending suggestion"""
    user = update.effective_user

    # Get user language
    user_lang = get_user_language(user.id)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(get_text("messages.banned", lang=user_lang), reply_markup=ReplyKeyboardRemove())
        return

    # Check cooldown for suggestions - PASS user_lang for localized error message!
    can_send, error_msg = feedback_service.check_cooldown(user.id, "suggestion", user_lang)
    if not can_send:
        await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
        return

    # Set state to wait for suggestion text
    context.user_data["state"] = "awaiting_suggestion"
    await update.message.reply_text(get_text("messages.write_suggestion", lang=user_lang), reply_markup=ReplyKeyboardRemove())


async def review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start sending review"""
    user = update.effective_user

    # Get user language
    user_lang = get_user_language(user.id)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(get_text("messages.banned", lang=user_lang), reply_markup=ReplyKeyboardRemove())
        return

    # Check cooldown for reviews - PASS user_lang for localized error message!
    can_send, error_msg = feedback_service.check_cooldown(user.id, "review", user_lang)
    if not can_send:
        await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
        return

    # Set state to wait for review text
    context.user_data["state"] = "awaiting_review"
    await update.message.reply_text(get_text("messages.write_review", lang=user_lang), reply_markup=ReplyKeyboardRemove())


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages from user"""
    user = update.effective_user
    text = update.message.text

    # Get user language
    user_lang = get_user_language(user.id)

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        await update.message.reply_text(get_text("messages.banned", lang=user_lang), reply_markup=ReplyKeyboardRemove())
        return

    # Get current user state
    state = context.user_data.get("state")

    # Handle different states
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
            # Debug logging
            logger.debug(f"🔍 Active ticket: {active_ticket.id}, last_actor={active_ticket.last_actor}, status={active_ticket.status}")

            # Check if waiting for admin reply (user wrote, waiting for admin response)
            if active_ticket.last_actor == "user":
                logger.warning(f"⏳ User {user.id} waiting for admin reply on ticket {active_ticket.id}")
                await update.message.reply_text(
                    get_text("messages.wait_for_admin_reply", lang=user_lang),
                    reply_markup=ReplyKeyboardRemove()
                )
                return

            # Send message to admin
            logger.info(f"✅ User {user.id} sending message to admin on ticket {active_ticket.id}")
            await handle_ticket_message(update, context, active_ticket.id, text)
        else:
            # Show menu if no active ticket
            from handlers.start import get_user_inline_menu
            await update.message.reply_text(
                get_text("messages.please_choose_from_menu", lang=user_lang),
                reply_markup=get_user_inline_menu(user_lang)
            )


async def handle_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle question text from user"""
    user = update.effective_user

    # Get user language
    user_lang = get_user_language(user.id)

    # Check minimum length
    if len(text) < ASK_MIN_LENGTH:
        await update.message.reply_text(
            get_text("messages.min_length", lang=user_lang, n=ASK_MIN_LENGTH),
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Create ticket from question
    ticket = ticket_service.create_ticket(
        user_id=user.id,
        initial_message=text,
        username=user.username
    )

    # Clear state
    context.user_data["state"] = None

    # Confirm to user
    await update.message.reply_text(
        get_text("messages.ticket_created", lang=user_lang, ticket_id=ticket.id),
        reply_markup=ReplyKeyboardRemove()
    )

    # Send ticket card to admin
    await send_or_update_ticket_card(context, ticket.id, action="new")


async def handle_suggestion_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle suggestion text from user"""
    user = update.effective_user

    # Get user language
    user_lang = get_user_language(user.id)

    # Get skip_cooldown flag
    skip_cooldown = context.user_data.get("skip_cooldown", False)

    # Check cooldown if not skipped - PASS user_lang!
    if not skip_cooldown:
        can_send, error_msg = feedback_service.check_cooldown(user.id, "suggestion", user_lang)
        if not can_send:
            await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
            return

        feedback_service.update_last_feedback(user.id, "suggestion")

    # Clear state
    context.user_data["state"] = None
    context.user_data["skip_cooldown"] = False

    # Confirm to user
    await update.message.reply_text(get_text("messages.suggestion_sent", lang=user_lang), reply_markup=ReplyKeyboardRemove())

    # Create feedback record
    feedback_id = feedback_service.create_feedback(user.id, "suggestion", text)

    try:
        # Get admin language for admin message
        admin_lang = get_admin_language()

        # Create keyboard with thank button - ACTIVE STATE
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text("admin.thank_suggestion", lang=admin_lang), callback_data=f"thank:{feedback_id}")]
        ])

        # Correct substitution of variables through .format()
        suggestion_header = get_text('admin.suggestion_from', lang=admin_lang).format(
            username=user.username or 'unknown',
            user_id=user.id
        )

        # Send suggestion to admin with proper localization
        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{suggestion_header}:\n\n{text}",
            reply_markup=keyboard
        )

        # Store message ID for later reference
        feedback_service.set_message_id(feedback_id, msg.message_id)
        logger.info(f"✅ Suggestion sent to admin: {feedback_id}")
    except Exception as e:
        logger.error(f"Failed to send suggestion alert: {e}", exc_info=True)


async def handle_review_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle review text from user"""
    user = update.effective_user

    # Get user language
    user_lang = get_user_language(user.id)

    # Get skip_cooldown flag
    skip_cooldown = context.user_data.get("skip_cooldown", False)

    # Check cooldown if not skipped - PASS user_lang!
    if not skip_cooldown:
        can_send, error_msg = feedback_service.check_cooldown(user.id, "review", user_lang)
        if not can_send:
            await update.message.reply_text(error_msg, reply_markup=ReplyKeyboardRemove())
            return

        feedback_service.update_last_feedback(user.id, "review")

    # Clear state
    context.user_data["state"] = None
    context.user_data["skip_cooldown"] = False

    # Confirm to user
    await update.message.reply_text(get_text("messages.review_sent", lang=user_lang), reply_markup=ReplyKeyboardRemove())

    # Create feedback record
    feedback_id = feedback_service.create_feedback(user.id, "review", text)

    try:
        # Get admin language for admin message
        admin_lang = get_admin_language()

        # Create keyboard with thank button - ACTIVE STATE
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text("admin.thank_review", lang=admin_lang), callback_data=f"thank:{feedback_id}")]
        ])

        # support substitution via .format()
        review_header = get_text('admin.review_from', lang=admin_lang).format(
            username=user.username or 'unknown',
            user_id=user.id
        )

        # Send review to admin with proper localization
        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{review_header}:\n\n{text}",
            reply_markup=keyboard
        )

        # Store message ID for later reference
        feedback_service.set_message_id(feedback_id, msg.message_id)
        logger.info(f"✅ Review sent to admin: {feedback_id}")
    except Exception as e:
        logger.error(f"Failed to send review alert: {e}", exc_info=True)


async def handle_ticket_message(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str, text: str):
    """Handle message in active ticket"""
    user = update.effective_user

    # Get user language
    user_lang = get_user_language(user.id)

    # Add message to ticket
    ticket_service.add_message(ticket_id, "user", text)

    # Confirm to user
    await update.message.reply_text(get_text("messages.message_sent", lang=user_lang), reply_markup=ReplyKeyboardRemove())

    # Get admin language
    admin_lang = get_admin_language()

    # Create button to open ticket
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text('search.button_open', lang=admin_lang), callback_data=f"ticket:{ticket_id}")]
    ])

    try:
        # Send notification to admin
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
    """Handle admin reply to ticket"""
    # Get ticket ID from context
    ticket_id = context.user_data.get("reply_ticket_id")

    if not ticket_id:
        return

    # Add reply to ticket
    ticket = ticket_service.add_message(ticket_id, "support", text, ADMIN_ID)

    if not ticket:
        user_lang = get_user_language(update.effective_user.id)
        await update.message.reply_text(get_text("messages.ticket_not_found", lang=user_lang), reply_markup=ReplyKeyboardRemove())
        return

    # Get user language for user message
    user_lang = get_user_language(ticket.user_id)

    # Clear state
    context.user_data["state"] = None
    context.user_data["reply_ticket_id"] = None

    # Get admin language
    admin_lang = get_admin_language()

    # Confirm to admin
    await update.message.reply_text(get_text("messages.answer_sent", lang=admin_lang), reply_markup=ReplyKeyboardRemove())

    try:
        # Send answer to user in their language
        await context.bot.send_message(
            chat_id=ticket.user_id,
            text=f"{get_text('messages.admin_reply', lang=user_lang)}\n\n{text}",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Failed to send message to user {ticket.user_id}: {e}")

    # Update ticket card
    message_id = TICKET_CARD_MESSAGES.get(ticket_id)
    await send_or_update_ticket_card(context, ticket_id, action="working", message_id=message_id)


async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media files (photos, videos, documents, etc.)"""
    user = update.effective_user

    # Check if user is banned
    if ban_manager.is_banned(user.id):
        return

    # Check if media is allowed from users
    if user.id != ADMIN_ID:
        if not ENABLE_MEDIA_FROM_USERS:
            user_lang = get_user_language(user.id)
            await update.message.reply_text(get_text("messages.media_not_allowed", lang=user_lang), reply_markup=ReplyKeyboardRemove())
            return

    # Get user language
    user_lang = get_user_language(user.id)

    # Determine media type
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

    # Get current state
    state = context.user_data.get("state")

    # Handle admin reply with media
    if state == "awaiting_reply":
        ticket_id = context.user_data.get("reply_ticket_id")
        if ticket_id:
            # Add media to ticket
            ticket = ticket_service.add_message(ticket_id, "support", f"[{media_type}]", ADMIN_ID)

            if ticket:
                # Clear state
                context.user_data["state"] = None
                context.user_data["reply_ticket_id"] = None

                # Get admin language
                admin_lang = get_admin_language()

                # Confirm to admin
                await update.message.reply_text(get_text("messages.answer_sent", lang=admin_lang), reply_markup=ReplyKeyboardRemove())

                try:
                    # Forward media to user
                    await update.message.forward(chat_id=ticket.user_id)
                except Exception as e:
                    logger.error(f"Failed to forward media to user {ticket.user_id}: {e}")

                # Update ticket card
                message_id = TICKET_CARD_MESSAGES.get(ticket_id)
                await send_or_update_ticket_card(context, ticket_id, action="working", message_id=message_id)
        return

    # Handle media in active ticket
    active_ticket = ticket_service.get_user_active_ticket(user.id)
    if active_ticket:
        # Check if waiting for admin reply
        if active_ticket.last_actor == "user":
            await update.message.reply_text(get_text("messages.wait_for_admin_reply", lang=user_lang), reply_markup=ReplyKeyboardRemove())
            return

        # Add media to ticket
        ticket_service.add_message(active_ticket.id, "user", f"[{media_type}]")

        # Confirm to user
        await update.message.reply_text(get_text("messages.message_sent", lang=user_lang), reply_markup=ReplyKeyboardRemove())

        # Get admin language
        admin_lang = get_admin_language()

        # Create button to open ticket
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📋 {get_text('search.button_open', lang=admin_lang)}", callback_data=f"ticket:{active_ticket.id}")]
        ])

        try:
            # Send notification to admin
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
    """Return to service menu"""
    user_lang = get_user_language(update.effective_user.id)
    context.user_data["state"] = None
    await update.message.reply_text(get_text("messages.return_to_menu", lang=user_lang), reply_markup=ReplyKeyboardRemove())


async def support_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to support menu"""
    user_lang = get_user_language(update.effective_user.id)
    context.user_data["state"] = None
    await update.message.reply_text(get_text("messages.return_to_support_menu", lang=user_lang), reply_markup=ReplyKeyboardRemove())
