import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from config import ADMIN_ID, PAGE_SIZE
from locales import get_text
from utils.locale_helper import get_admin_language
from services.tickets import ticket_service
from services.bans import ban_manager
from storage.data_manager import data_manager
from storage.instruction_store import ADMIN_SCREEN_MESSAGES
from utils.formatters import format_ticket_brief, format_ticket_card, format_ticket_preview
from utils.admin_screen import show_admin_screen, reset_admin_screen, clear_all_admin_screens
from utils.states import (
    STATE_SEARCH_TICKET_INPUT,
    STATE_AWAITING_BAN_USER_ID,
    STATE_AWAITING_BAN_REASON,
    STATE_AWAITING_UNBAN_USER_ID,
    STATE_AWAITING_REPLY,
)
from utils.admin_help import get_admin_help_text
from utils.keyboards import get_admin_help_keyboard

logger = logging.getLogger(__name__)


async def inbox_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Entry point for admin inbox.

    Resets filter and page to defaults and shows the inbox list.
    """
    user = update.effective_user

    if user.id != ADMIN_ID:
        return

    context.user_data["inbox_filter"] = "all"
    context.user_data["inbox_page"] = 0

    await show_inbox(update, context)


async def show_inbox(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_filter: str | None = None,
    page: int | None = None,
) -> None:
    """
    Display ticket list for admin with pagination and status filter.

    - Tickets can be filtered by status: all/new/working/done.
    - Tickets are sorted so that tickets where support's turn comes first,
      then by creation time (newer tickets above).
    - Uses PAGE_SIZE from config for pagination.
    """
    user_lang = get_admin_language()

    logger.info("DEBUG: PAGE_SIZE = %s", PAGE_SIZE)

    if status_filter is not None:
        filter_status = status_filter
        context.user_data["inbox_filter"] = status_filter
    else:
        filter_status = context.user_data.get("inbox_filter", "all")

    if page is not None:
        current_page = page
        context.user_data["inbox_page"] = page
    else:
        current_page = context.user_data.get("inbox_page", 0)

    if filter_status == "all":
        tickets = data_manager.get_all_tickets()
    else:
        tickets = data_manager.get_tickets_by_status(filter_status)

    # Sorting rules:
    # 1. Tickets where last_actor == "user" (support's turn) go first.
    # 2. Inside each group, newer tickets go above older ones.
    def sort_key(t):
        waiting_support = 0 if getattr(t, "last_actor", None) == "user" else 1
        try:
            ts = t.created_at.timestamp()
        except Exception:
            ts = 0
        return (waiting_support, -ts)

    tickets = sorted(tickets, key=sort_key)

    total_tickets = len(tickets)
    total_pages = max(1, (total_tickets + PAGE_SIZE - 1) // PAGE_SIZE)
    start_idx = current_page * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_tickets)
    page_tickets = tickets[start_idx:end_idx]

    logger.info(
        "DEBUG: total_tickets=%s, page=%s, start_idx=%s, end_idx=%s, showing=%s",
        total_tickets,
        current_page,
        start_idx,
        end_idx,
        len(page_tickets),
    )

    filter_names = {
        "all": get_text("inbox.filter_all", lang=user_lang),
        "new": get_text("inbox.filter_new", lang=user_lang),
        "working": get_text("inbox.filter_working", lang=user_lang),
        "done": get_text("inbox.filter_done", lang=user_lang),
    }
    filter_display = filter_names.get(filter_status, filter_status)

    if not page_tickets:
        text = (
            f"**{get_text('inbox.title', lang=user_lang)}** "
            f"({filter_display})\n\n"
            f"{get_text('inbox.no_tickets', lang=user_lang)}"
        )
    else:
        header = (
            f"**{get_text('inbox.title', lang=user_lang)}** "
            f"({filter_display}) | "
            f"{get_text('inbox.page', lang=user_lang, page=current_page + 1, total=total_pages)}\n\n"
        )
        previews = [format_ticket_preview(t) for t in page_tickets]
        text = header + "\n".join(previews)

    # Filter buttons row
    filter_row: list[InlineKeyboardButton] = []
    for flt in ["all", "new", "working", "done"]:
        label = filter_names[flt]
        prefix = "✅ " if flt == filter_status else ""
        filter_row.append(
            InlineKeyboardButton(
                f"{prefix}{label}",
                callback_data=f"inbox_filter:{flt}",
            )
        )

    # Pagination row (back/forward)
    nav_row: list[InlineKeyboardButton] = []
    if current_page > 0:
        nav_row.append(
            InlineKeyboardButton(
                get_text("buttons.back", lang=user_lang),
                callback_data=f"inbox_page:{current_page - 1}",
            )
        )
    if current_page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                get_text("buttons.forward", lang=user_lang),
                callback_data=f"inbox_page:{current_page + 1}",
            )
        )

    # Search row
    search_row = [
        InlineKeyboardButton(
            get_text("search.button", lang=user_lang),
            callback_data="search_ticket_start",
        )
    ]

    # Home row
    home_row = [
        InlineKeyboardButton(
            get_text("buttons.main_menu", lang=user_lang),
            callback_data="admin_home",
        )
    ]

    keyboard_rows: list[list[InlineKeyboardButton]] = [filter_row]
    if nav_row:
        keyboard_rows.append(nav_row)
    keyboard_rows.append(search_row)
    keyboard_rows.append(home_row)

    keyboard = InlineKeyboardMarkup(keyboard_rows)

    await show_admin_screen(update, context, text, keyboard, screen_type="inbox")


async def show_ticket_card(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str
) -> None:
    """
    Display full ticket card for admin.

    Shows full ticket details and context actions depending on ticket status:
    - New: Take in work, Close.
    - Working: Reply, Close.
    """
    user_lang = get_admin_language()

    ticket = ticket_service.get_ticket(ticket_id)

    if not ticket:
        await show_admin_screen(
            update,
            context,
            get_text("messages.ticket_not_found", lang=user_lang),
            None,
            screen_type="ticket",
        )
        return

    text = format_ticket_card(ticket)

    actions: list[list[InlineKeyboardButton]] = []

    if ticket.status == "new":
        actions.append(
            [
                InlineKeyboardButton(
                    get_text("buttons.take", lang=user_lang),
                    callback_data=f"take:{ticket_id}",
                ),
                InlineKeyboardButton(
                    get_text("buttons.close", lang=user_lang),
                    callback_data=f"close:{ticket_id}",
                ),
            ]
        )
    elif ticket.status == "working":
        actions.append(
            [
                InlineKeyboardButton(
                    get_text("buttons.reply", lang=user_lang),
                    callback_data=f"reply:{ticket_id}",
                ),
                InlineKeyboardButton(
                    get_text("buttons.close", lang=user_lang),
                    callback_data=f"close:{ticket_id}",
                ),
            ]
        )

    # Back to inbox
    actions.append(
        [
            InlineKeyboardButton(
                get_text("buttons.back", lang=user_lang),
                callback_data="admin_inbox",
            )
        ]
    )
    # Back to main admin menu
    actions.append(
        [
            InlineKeyboardButton(
                get_text("buttons.main_menu", lang=user_lang),
                callback_data="admin_home",
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(actions)

    await show_admin_screen(update, context, text, keyboard, screen_type="ticket")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display bot statistics screen for admin.

    Includes:
    - total users / tickets,
    - active / closed tickets,
    - tickets waiting for auto-close,
    - rating stats and banned users count.
    """
    user = update.effective_user
    user_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    stats = data_manager.get_stats()
    banned_count = len(ban_manager.get_banned_list())
    stats["banned_count"] = banned_count

    text = get_text("admin.stats_text", lang=user_lang, **stats)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_text("buttons.main_menu", lang=user_lang),
                    callback_data="admin_home",
                )
            ]
        ]
    )

    await show_admin_screen(update, context, text, keyboard, screen_type="stats")


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display settings menu for admin.

    Includes:
    - ban/unban,
    - bans list,
    - clear active tickets,
    - create backup,
    - info/debug screens,
    - change language.
    """
    user = update.effective_user
    user_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    from utils.keyboards import get_settings_keyboard

    await show_admin_screen(
        update,
        context,
        get_text("admin.settings", lang=user_lang),
        get_settings_keyboard(user_lang),
        screen_type="settings",
    )


async def home_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display admin main menu.

    Uses inline keyboard with:
    - Inbox,
    - Statistics,
    - Settings,
    - Help (admin instructions + donate).
    """
    user = update.effective_user
    user_lang = get_admin_language()

    if user.id != ADMIN_ID:
        return

    from utils.keyboards import get_admin_main_keyboard

    await show_admin_screen(
        update,
        context,
        get_text("admin.welcome", lang=user_lang),
        get_admin_main_keyboard(user_lang),
        screen_type="home",
    )


async def admin_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display detailed admin help screen with donate button.

    Text is locale-aware (ru/en) and describes:
    - Inbox and ticket card,
    - Take in work / Reply / Close,
    - Auto-close logic,
    - Statistics, backups, logs,
    - Bans and languages,
    - Optional project support (donation).
    """
    user = update.effective_user

    if user.id != ADMIN_ID:
        return

    text = get_admin_help_text()
    keyboard = get_admin_help_keyboard()

    await show_admin_screen(
        update,
        context,
        text,
        keyboard,
        screen_type="help",
    )


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle plain text messages from admin.

    This handler is state-driven:
    - STATE_SEARCH_TICKET_INPUT: search ticket by ID.
    - STATE_AWAITING_BAN_USER_ID: read user ID to ban.
    - STATE_AWAITING_BAN_REASON: read ban reason and apply ban.
    - STATE_AWAITING_UNBAN_USER_ID: read user ID to unban.
    - STATE_AWAITING_REPLY: admin reply to user ticket.
    - default: show a short instruction hint.
    """
    user = update.effective_user
    user_lang = get_admin_language()
    text = update.message.text

    if user.id != ADMIN_ID:
        return

    state = context.user_data.get("state")
    logger.info(
        "DEBUG admin_text_handler: user_id=%s, state=%s, text=%s",
        user.id,
        state,
        text[:20],
    )

    # --- Search ticket by ID ---
    if state == STATE_SEARCH_TICKET_INPUT:
        search_input = text.strip().replace("#", "")
        tickets_list = data_manager.get_all_tickets()

        found_ticket = None
        for ticket in tickets_list:
            if search_input in ticket.id:
                found_ticket = ticket
                break

        context.user_data["state"] = None

        search_menu_msg_id = context.user_data.get("search_menu_msg_id")

        try:
            await update.message.delete()
            logger.info("Deleted admin search input message")
        except Exception as e:
            logger.debug("Search input message already deleted: %s", e)

        if search_menu_msg_id:
            if not found_ticket:
                # Update existing search message: not found
                try:
                    await context.bot.edit_message_text(
                        chat_id=ADMIN_ID,
                        message_id=search_menu_msg_id,
                        text=get_text(
                            "search.not_found",
                            lang=user_lang,
                            ticket_number=search_input,
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        text=get_text(
                                            "search.button_new_search",
                                            lang=user_lang,
                                        ),
                                        callback_data="search_ticket_start",
                                    ),
                                    InlineKeyboardButton(
                                        text=get_text(
                                            "search.button_cancel",
                                            lang=user_lang,
                                        ),
                                        callback_data="admin_inbox",
                                    ),
                                ]
                            ]
                        ),
                        parse_mode="HTML",
                    )
                    logger.info(
                        "Updated search result (not found): %s",
                        search_menu_msg_id,
                    )
                    return
                except Exception as e:
                    logger.error(
                        "Failed to edit search result (not found): %s", e
                    )
            else:
                # Update existing search message: found ticket
                try:
                    await context.bot.edit_message_text(
                        chat_id=ADMIN_ID,
                        message_id=search_menu_msg_id,
                        text=format_ticket_preview(found_ticket),
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        text=get_text(
                                            "search.button_open",
                                            lang=user_lang,
                                        ),
                                        callback_data=f"ticket:{found_ticket.id}",
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        text=get_text(
                                            "search.button_new_search",
                                            lang=user_lang,
                                        ),
                                        callback_data="search_ticket_start",
                                    ),
                                    InlineKeyboardButton(
                                        text=get_text(
                                            "search.button_cancel",
                                            lang=user_lang,
                                        ),
                                        callback_data="admin_inbox",
                                    ),
                                ],
                            ]
                        ),
                        parse_mode="HTML",
                    )
                    logger.info(
                        "Updated search result (found): %s",
                        search_menu_msg_id,
                    )
                    return
                except Exception as e:
                    logger.error(
                        "Failed to edit search result (found): %s", e
                    )

        # Fallback: send new message if we failed to update existing one
        if not found_ticket:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=get_text(
                    "search.not_found",
                    lang=user_lang,
                    ticket_number=search_input,
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=get_text(
                                    "search.button_new_search",
                                    lang=user_lang,
                                ),
                                callback_data="search_ticket_start",
                            ),
                            InlineKeyboardButton(
                                text=get_text(
                                    "search.button_cancel",
                                    lang=user_lang,
                                ),
                                callback_data="admin_inbox",
                            ),
                        ]
                    ]
                ),
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=format_ticket_preview(found_ticket),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=get_text(
                                    "search.button_open", lang=user_lang
                                ),
                                callback_data=f"ticket:{found_ticket.id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=get_text(
                                    "search.button_new_search",
                                    lang=user_lang,
                                ),
                                callback_data="search_ticket_start",
                            ),
                            InlineKeyboardButton(
                                text=get_text(
                                    "search.button_cancel",
                                    lang=user_lang,
                                ),
                                callback_data="admin_inbox",
                            ),
                        ],
                    ]
                ),
            )
        return

    # --- Handle ban user ID input ---
    if state == STATE_AWAITING_BAN_USER_ID:
        try:
            user_id = int(text.strip())
            context.user_data["ban_user_id"] = user_id
            context.user_data["state"] = STATE_AWAITING_BAN_REASON

            await update.message.reply_text(
                get_text("admin.enter_ban_reason", lang=user_lang)
            )
        except ValueError:
            await update.message.reply_text(
                get_text("messages.invalid_id_format", lang=user_lang)
            )
            return

    # --- Handle ban reason input ---
    elif state == STATE_AWAITING_BAN_REASON:
        user_id = context.user_data.get("ban_user_id")
        if user_id:
            if ban_manager.is_banned(user_id):
                ban_reason = ban_manager.get_ban_reason(user_id)

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                get_text("buttons.back", lang=user_lang),
                                callback_data="admin_settings",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                get_text(
                                    "buttons.main_menu", lang=user_lang
                                ),
                                callback_data="admin_home",
                            )
                        ],
                    ]
                )

                await update.message.reply_text(
                    get_text(
                        "admin.user_already_banned_reason",
                        lang=user_lang,
                    ).format(user_id=user_id, reason=ban_reason),
                    reply_markup=keyboard,
                )
                context.user_data["state"] = None
                return

            ban_manager.ban_user(user_id, text)
            context.user_data["state"] = None

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            get_text("buttons.back", lang=user_lang),
                            callback_data="admin_settings",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            get_text(
                                "buttons.main_menu", lang=user_lang
                            ),
                            callback_data="admin_home",
                        )
                    ],
                ]
            )

            await update.message.reply_text(
                get_text("admin.user_banned", lang=user_lang).format(
                    user_id=user_id, reason=text
                ),
                reply_markup=keyboard,
            )
        return

    # --- Handle unban user ID input ---
    elif state == STATE_AWAITING_UNBAN_USER_ID:
        try:
            user_id = int(text.strip())

            if not ban_manager.is_banned(user_id):
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                get_text("buttons.back", lang=user_lang),
                                callback_data="admin_settings",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                get_text(
                                    "buttons.main_menu", lang=user_lang
                                ),
                                callback_data="admin_home",
                            )
                        ],
                    ]
                )

                await update.message.reply_text(
                    get_text("admin.user_not_banned", lang=user_lang).format(
                        user_id=user_id
                    ),
                    reply_markup=keyboard,
                )
                context.user_data["state"] = None
                return

            ban_reason = ban_manager.get_ban_reason(user_id)
            ban_manager.unban_user(user_id)
            context.user_data["state"] = None

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            get_text("buttons.back", lang=user_lang),
                            callback_data="admin_settings",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            get_text(
                                "buttons.main_menu", lang=user_lang
                            ),
                            callback_data="admin_home",
                        )
                    ],
                ]
            )

            await update.message.reply_text(
                get_text(
                    "admin.user_unbanned_reason", lang=user_lang
                ).format(user_id=user_id, reason=ban_reason),
                reply_markup=keyboard,
            )
        except ValueError:
            await update.message.reply_text(
                get_text("messages.invalid_id_format", lang=user_lang)
            )
        return

    # --- Handle admin reply to ticket (plain text) ---
    elif state == STATE_AWAITING_REPLY:
        from handlers.user import handle_admin_reply

        await handle_admin_reply(update, context, text)
        return

    # --- Default: show small hint for admin ---
    else:
        msg = await update.message.reply_text(
            get_text("admin.reply_instruction", lang=user_lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        logger.info("Admin needs guidance: %s", msg.message_id)


# Aliases for main.py compatibility
admin_inbox = inbox_handler
admin_stats = stats_handler
admin_settings = settings_handler
admin_home = home_handler
admin_help = admin_help_handler
