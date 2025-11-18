import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import AUTO_CLOSE_AFTER_HOURS, TIMEZONE
from storage.data_manager import data_manager
from services.alerts import alert_service
from services.tickets import ticket_service
from utils.locale_helper import get_admin_language, get_user_language
from utils.formatters import format_ticket_card
from locales import _ , get_text

logger = logging.getLogger(__name__)


async def auto_close_inactive_tickets() -> None:
    """
    Check and automatically close inactive tickets.

    Closes tickets only when:
    1. Last actor was admin/support
    2. No user response after AUTO_CLOSE_AFTER_HOURS hours
    3. Ticket status is 'new' or 'working'

    Sends notifications to admin and users about auto-closed tickets.
    """
    try:
        now = datetime.now(TIMEZONE)
        threshold = now - timedelta(hours=AUTO_CLOSE_AFTER_HOURS)
        closed_tickets: list[dict] = []

        all_tickets = data_manager.get_all_tickets()
        open_tickets = [t for t in all_tickets if t.status in ["new", "working"]]

        logger.debug("Checking %d open tickets for auto-close", len(open_tickets))

        for ticket in open_tickets:
            # Only close if last actor was support (admin replied last)
            if ticket.last_actor != "support":
                logger.debug(
                    "Ticket %s skipped: last actor was '%s', not 'support' (waiting for user reply)",
                    ticket.id,
                    ticket.last_actor,
                )
                continue

            last_activity = ticket.last_activity_at

            if not last_activity:
                last_activity = ticket.created_at
                logger.warning(
                    "Ticket %s has no last_activity_at, using created_at", ticket.id
                )

            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=TIMEZONE)

            if last_activity < threshold:
                hours_inactive = (now - last_activity).total_seconds() / 3600

                logger.info(
                    "Auto-closing ticket %s (admin replied, no user response for %.1f hours, last activity: %s)",
                    ticket.id,
                    hours_inactive,
                    last_activity.strftime("%Y-%m-%d %H:%M:%S"),
                )

                ticket.status = "done"
                ticket.last_activity_at = now
                data_manager.update_ticket(ticket)

                closed_tickets.append(
                    {
                        "id": ticket.id,
                        "user_id": ticket.user_id,
                        "hours_inactive": hours_inactive,
                    }
                )

        if not closed_tickets:
            logger.debug("No inactive tickets to auto-close")
            return

        logger.info("Auto-closed %d inactive ticket(s)", len(closed_tickets))

        admin_lang = get_admin_language()

        for ticket_info in closed_tickets:
            ticket_id = ticket_info["id"]
            user_id = ticket_info["user_id"]

            # 1) Admin: alert + ticket card
            try:
                ticket = ticket_service.get_ticket(ticket_id)
                if ticket:
                    card_text = format_ticket_card(ticket)
                    header = _(
                        "alerts.ticket_auto_closed",
                        ticket_id=ticket_id,
                        hours=AUTO_CLOSE_AFTER_HOURS,
                    )
                    text = f"{header}\n\n{card_text}"
                else:
                    text = _(
                        "alerts.ticket_auto_closed",
                        ticket_id=ticket_id,
                        hours=AUTO_CLOSE_AFTER_HOURS,
                    )

                await alert_service.send_alert(text)
                logger.info(
                    "Sent auto-close alert for ticket %s to admin",
                    ticket_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to send auto-close alert for %s: %s",
                    ticket_id,
                    e,
                    exc_info=True,
                )

            # 2) User: auto-close notification + button to create new ticket
            try:
                user_lang = get_user_language(user_id)
                user_message = _(
                    "messages.ticket_auto_closed_user",
                    ticket_id=ticket_id,
                    hours=AUTO_CLOSE_AFTER_HOURS,
                )

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                get_text("buttons.ask_question", lang=user_lang),
                                callback_data="user_start_question",
                            )
                        ]
                    ]
                )

                await alert_service.send_user_message(
                    user_id, user_message, reply_markup=keyboard
                )
                logger.info(
                    "Sent auto-close notification to user %s for ticket %s",
                    user_id,
                    ticket_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to send auto-close notification to user %s: %s",
                    user_id,
                    e,
                    exc_info=True,
                )

    except Exception as e:
        logger.error("Error in auto_close_inactive_tickets: %s", e, exc_info=True)
