import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_ID, PAGE_SIZE, DEFAULT_LOCALE
from locales import get_text
from utils.locale_helper import get_user_language, get_admin_language
from services.tickets import ticket_service
from services.bans import ban_manager
from storage.data_manager import data_manager
from storage.instruction_store import ADMIN_SCREEN_MESSAGES
from utils.formatters import format_ticket_brief, format_ticket_card, format_ticket_preview
from utils.admin_screen import show_admin_screen, reset_admin_screen, clear_all_admin_screens

logger = logging.getLogger(__name__)


async def inbox_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming tickets inbox"""
    user = update.effective_user

    if user.id != ADMIN_ID:
        return

    context.user_data["inbox_filter"] = "all"
    context.user_data["inbox_page"] = 0

    await show_inbox(update, context)


async def show_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display ticket list with pagination and filtering"""
    user = update.effective_user
    # Get admin language instead of user language
    user_lang = get_admin_language()

    logger.info(f"🔍 DEBUG: PAGE_SIZE = {PAGE_SIZE}")

    filter_status = context.user_data.get("inbox_filter", "all")
    page = context.user_data.get("inbox_page", 0)

    # Fetch tickets based on filter status
    if filter_status == "all":
        tickets = data_manager.get_all_tickets()
    else:
        tickets = data_manager.get_tickets_by_status(filter_status)

    # Sort tickets by creation date (newest first)
    tickets = sorted(tickets, key=lambda t: t.created_at, reverse=True)

    # Calculate pagination
    total_tickets = len(tickets)
    total_pages = max(1, (total_tickets + PAGE_SIZE - 1) // PAGE_SIZE)
    start_idx = page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_tickets)
    page_tickets = tickets[start_idx:end_idx]

    logger.info(f"🔍 DEBUG: total_tickets={total_tickets}, page={page}, start_idx={start_idx}, end_idx={end_idx}, showing={len(page_tickets)}")

    # Translate filter status names
    filter_names = {
        "all": get_text("inbox.filter_all", lang=user_lang),
        "new": get_text("inbox.filter_new", lang=user_lang),
        "working": get_text("inbox.filter_working", lang=user_lang),
        "done": get_text("inbox.filter_done", lang=user_lang)
    }
    filter_display = filter_names.get(filter_status, filter_status)

    # Format message text
    if not page_tickets:
        text = f"**{get_text('inbox.title', lang=user_lang)}** ({filter_display})\n\n{get_text('inbox.no_tickets', lang=user_lang)}"
    else:
        header = f"**{get_text('inbox.title', lang=user_lang)}** ({filter_display}) | {get_text('inbox.page', lang=user_lang, page=page+1, total=total_pages)}\n\n"
        previews = [format_ticket_preview(t) for t in page_tickets]
        text = header + "\n".join(previews)

    # Build filter buttons
    filter_row = []
    for flt in ["all", "new", "working", "done"]:
        label = filter_names[flt]
        prefix = "✅ " if flt == filter_status else ""
        filter_row.append(
            InlineKeyboardButton(
                f"{prefix}{label}",
                callback_data=f"inbox_filter:{flt}"
            )
        )

    # Build pagination buttons
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data=f"inbox_page:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(get_text('buttons.forward', lang=user_lang), callback_data=f"inbox_page:{page+1}"))

    # Search button (with localization)
    search_row = [InlineKeyboardButton(get_text("search.button", lang=user_lang), callback_data="search_ticket_start")]

    # Main menu button (NO EXTRA EMOJI!)
    home_row = [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]

    # Build complete keyboard
    keyboard_rows = [filter_row]
    if nav_row:
        keyboard_rows.append(nav_row)
    keyboard_rows.append(search_row)
    keyboard_rows.append(home_row)

    keyboard = InlineKeyboardMarkup(keyboard_rows)

    await show_admin_screen(update, context, text, keyboard, screen_type="inbox")


async def show_ticket_card(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str):
    """Display full ticket card"""
    user = update.effective_user
    user_lang = get_admin_language()

    ticket = ticket_service.get_ticket(ticket_id)

    if not ticket:
        await show_admin_screen(update, context, get_text("messages.ticket_not_found", lang=user_lang), None, screen_type="ticket")
        return

    text = format_ticket_card(ticket)

    # Build action buttons based on ticket status
    actions = []

    if ticket.status == "new":
        # Row 1: Take + Close (side by side)
        actions.append([
            InlineKeyboardButton(get_text("buttons.take", lang=user_lang), callback_data=f"take:{ticket_id}"),
            InlineKeyboardButton(get_text("buttons.close", lang=user_lang), callback_data=f"close:{ticket_id}")
        ])
    elif ticket.status == "working":
        # Row 1: Reply + Close (side by side)
        actions.append([
            InlineKeyboardButton(get_text("buttons.reply", lang=user_lang), callback_data=f"reply:{ticket_id}"),
            InlineKeyboardButton(get_text("buttons.close", lang=user_lang), callback_data=f"close:{ticket_id}")
        ])

    # Back button (no extra emoji!)
    actions.append([InlineKeyboardButton(get_text("buttons.back", lang=user_lang), callback_data="admin_inbox")])

    # Main menu button (no extra emoji!)
    actions.append([InlineKeyboardButton(get_text("buttons.main_menu", lang=user_lang), callback_data="admin_home")])

    keyboard = InlineKeyboardMarkup(actions)

    await show_admin_screen(update, context, text, keyboard, screen_type="ticket")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display statistics"""
    user = update.effective_user
    user_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    stats = data_manager.get_stats()
    banned_count = len(ban_manager.get_banned_list())
    stats["banned_count"] = banned_count

    text = get_text("admin.stats_text", lang=user_lang, **stats)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]
    ])

    await show_admin_screen(update, context, text, keyboard, screen_type="stats")


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display settings menu"""
    user = update.effective_user
    user_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    from utils.keyboards import get_settings_keyboard

    await show_admin_screen(
        update, context,
        get_text("admin.settings", lang=user_lang),
        get_settings_keyboard(user_lang),
        screen_type="settings"
    )


async def home_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin main menu"""
    user = update.effective_user
    user_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    from utils.keyboards import get_admin_main_keyboard

    await show_admin_screen(
        update, context,
        get_text("admin.welcome", lang=user_lang),
        get_admin_main_keyboard(user_lang),
        screen_type="home"
    )


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages from admin"""
    user = update.effective_user
    user_lang = get_admin_language()
    text = update.message.text

    if user.id != ADMIN_ID:
        return

    state = context.user_data.get("state")
    logger.info(f"🔍 DEBUG admin_text_handler: user_id={user.id}, state={state}, text={text[:20]}")

    # Search ticket by ID
    if state == "search_ticket_input":
        search_input = text.strip().replace("#", "")
        tickets_list = data_manager.get_all_tickets()

        # Find ticket by ID match
        found_ticket = None
        for ticket in tickets_list:
            if search_input in ticket.id:
                found_ticket = ticket
                break

        context.user_data["state"] = None

        # GET SAVED message_id (SAME MESSAGE)
        search_menu_msg_id = context.user_data.get("search_menu_msg_id")

        # Delete only ADMIN'S TEXT (his input)
        try:
            await update.message.delete()
            logger.info(f"✅ Deleted admin search input message")
        except Exception as e:
            logger.debug(f"Search input message already deleted: {e}")

        # EDIT IN PLACE (don't create new message!)
        if search_menu_msg_id:
            if not found_ticket:
                try:
                    await context.bot.edit_message_text(
                        chat_id=ADMIN_ID,
                        message_id=search_menu_msg_id,
                        text=get_text("search.not_found", lang=user_lang, ticket_number=search_input),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(text=get_text("search.button_new_search", lang=user_lang), callback_data="search_ticket_start"),
                            InlineKeyboardButton(text=get_text("search.button_cancel", lang=user_lang), callback_data="admin_inbox")
                        ]]),
                        parse_mode='HTML'
                    )
                    logger.info(f"✅ Updated search result (not found): {search_menu_msg_id}")
                    return
                except Exception as e:
                    logger.error(f"Failed to edit search result: {e}")
            else:
                # Ticket found - edit in place
                try:
                    await context.bot.edit_message_text(
                        chat_id=ADMIN_ID,
                        message_id=search_menu_msg_id,
                        text=format_ticket_preview(found_ticket),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(text=get_text("search.button_open", lang=user_lang), callback_data=f"ticket:{found_ticket.id}")],
                            [
                                InlineKeyboardButton(text=get_text("search.button_new_search", lang=user_lang), callback_data="search_ticket_start"),
                                InlineKeyboardButton(text=get_text("search.button_cancel", lang=user_lang), callback_data="admin_inbox")
                            ]
                        ]),
                        parse_mode='HTML'
                    )
                    logger.info(f"✅ Updated search result (found): {search_menu_msg_id}")
                    return
                except Exception as e:
                    logger.error(f"Failed to edit search result: {e}")

        # Fallback: если нет search_menu_msg_id Create new message
        if not found_ticket:
            msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=get_text("search.not_found", lang=user_lang, ticket_number=search_input),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(text=get_text("search.button_new_search", lang=user_lang), callback_data="search_ticket_start"),
                    InlineKeyboardButton(text=get_text("search.button_cancel", lang=user_lang), callback_data="admin_inbox")
                ]])
            )
        else:
            msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=format_ticket_preview(found_ticket),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(text=get_text("search.button_open", lang=user_lang), callback_data=f"ticket:{found_ticket.id}")],
                    [
                        InlineKeyboardButton(text=get_text("search.button_new_search", lang=user_lang), callback_data="search_ticket_start"),
                        InlineKeyboardButton(text=get_text("search.button_cancel", lang=user_lang), callback_data="admin_inbox")
                    ]
                ])
            )
        return

    # Handle ban user ID input
    if state == "awaiting_ban_user_id":
        try:
            user_id = int(text.strip())
            context.user_data["ban_user_id"] = user_id
            context.user_data["state"] = "awaiting_ban_reason"

            await update.message.reply_text(get_text("admin.enter_ban_reason", lang=user_lang))
        except ValueError:
            await update.message.reply_text(get_text("messages.invalid_id_format", lang=user_lang))
            return

    # Handle ban reason input
    elif state == "awaiting_ban_reason":
        user_id = context.user_data.get("ban_user_id")
        if user_id:
            # CHECK - is already banned? AND GET REASON!
            banned_list = ban_manager.get_banned_list()
            ban_reason = None

            for banned_user_id, reason in banned_list:
                if banned_user_id == user_id:
                    ban_reason = reason
                    break

            if ban_reason:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="admin_settings")],
                    [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]
                ])

                # Added .format()
                await update.message.reply_text(
                    get_text("admin.user_already_banned_reason", lang=user_lang).format(user_id=user_id, reason=ban_reason),
                    reply_markup=keyboard
                )
                context.user_data["state"] = None
                return

            ban_manager.ban_user(user_id, text)
            context.user_data["state"] = None

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="admin_settings")],
                [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]
            ])

            # Added .format()
            await update.message.reply_text(
                get_text("admin.user_banned", lang=user_lang).format(user_id=user_id, reason=text),
                reply_markup=keyboard
            )
        return

    # Handle unban user ID input
    elif state == "awaiting_unban_user_id":
        try:
            user_id = int(text.strip())

            # CHECK - is banned at all? AND GET REASON!
            banned_list = ban_manager.get_banned_list()
            ban_reason = None

            for banned_user_id, reason in banned_list:
                if banned_user_id == user_id:
                    ban_reason = reason
                    break

            if not ban_reason:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="admin_settings")],
                    [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]
                ])

                # Added .format()
                await update.message.reply_text(
                    get_text("admin.user_not_banned", lang=user_lang).format(user_id=user_id),
                    reply_markup=keyboard
                )
                context.user_data["state"] = None
                return

            ban_manager.unban_user(user_id)
            context.user_data["state"] = None

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text('buttons.back', lang=user_lang), callback_data="admin_settings")],
                [InlineKeyboardButton(get_text('buttons.main_menu', lang=user_lang), callback_data="admin_home")]
            ])

            # Added .format()
            await update.message.reply_text(
                get_text("admin.user_unbanned_reason", lang=user_lang).format(user_id=user_id, reason=ban_reason),
                reply_markup=keyboard
            )
        except ValueError:
            await update.message.reply_text(get_text("messages.invalid_id_format", lang=user_lang))
        return

    # Handle admin reply to ticket
    elif state == "awaiting_reply":
        from handlers.user import handle_admin_reply
        await handle_admin_reply(update, context, text)
        return

    # Default instruction message
    else:
        msg = await update.message.reply_text(
            get_text("admin.reply_instruction", lang=user_lang),
            reply_markup=ReplyKeyboardRemove()
        )
        logger.info(f"Admin needs guidance: {msg.message_id}")


# Aliases for main.py compatibility
admin_inbox = inbox_handler
admin_stats = stats_handler
admin_settings = settings_handler
admin_home = home_handler
