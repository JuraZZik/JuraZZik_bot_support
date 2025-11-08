#!/usr/bin/env python3
"""
Ticket auto-close service

Automatically closes inactive tickets after configured timeout.
Only closes tickets where admin sent last message and user didn't reply.
"""

import logging
from datetime import datetime, timedelta
from config import AUTO_CLOSE_AFTER_HOURS, TIMEZONE, ADMIN_ID
from storage.data_manager import data_manager
from services.alerts import alert_service
from locales import _, set_locale

logger = logging.getLogger(__name__)


async def auto_close_inactive_tickets():
    """
    Check and automatically close inactive tickets

    Closes tickets only when:
    1. Last actor was admin/support
    2. No user response after AUTO_CLOSE_AFTER_HOURS hours
    3. Ticket status is 'new' or 'working'

    Sends notifications to admin and users about auto-closed tickets.
    """
    try:
        now = datetime.now(TIMEZONE)
        threshold = now - timedelta(hours=AUTO_CLOSE_AFTER_HOURS)
        closed_tickets = []

        # Get all open tickets (new or working status)
        all_tickets = data_manager.get_all_tickets()
        open_tickets = [t for t in all_tickets if t.status in ["new", "working"]]

        logger.debug(f"Checking {len(open_tickets)} open tickets for auto-close")

        for ticket in open_tickets:
            # Check if last actor was support (admin replied last)
            if ticket.last_actor != "support":
                logger.debug(
                    f"Ticket {ticket.id} skipped: last actor was '{ticket.last_actor}', "
                    f"not 'support' (waiting for user reply)"
                )
                continue

            # Get last activity time
            last_activity = ticket.last_activity_at

            if not last_activity:
                # Fallback to creation time if no last_activity
                last_activity = ticket.created_at
                logger.warning(
                    f"Ticket {ticket.id} has no last_activity_at, using created_at"
                )

            # Make timezone-aware if needed
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=TIMEZONE)

            # Check if ticket should be auto-closed
            # Close only if admin replied and user didn't respond for N hours
            if last_activity < threshold:
                hours_inactive = (now - last_activity).total_seconds() / 3600

                logger.info(
                    f"Auto-closing ticket {ticket.id} "
                    f"(admin replied, no user response for {hours_inactive:.1f} hours, "
                    f"last activity: {last_activity.strftime('%Y-%m-%d %H:%M:%S')})"
                )

                # Close the ticket
                ticket.status = "done"
                ticket.last_activity_at = now

                # Save ticket
                data_manager.update_ticket(ticket)

                closed_tickets.append({
                    'id': ticket.id,
                    'user_id': ticket.user_id,
                    'hours_inactive': hours_inactive
                })

        # Log results
        if closed_tickets:
            logger.info(f"Auto-closed {len(closed_tickets)} inactive ticket(s)")

            # Send notifications for each closed ticket
            for ticket_info in closed_tickets:
                # Send notification to admin (as ticket card with action)
                try:
                    from services.tickets import ticket_service
                    from utils.formatters import format_ticket_card
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                    # Load admin locale for ticket card
                    user_data = data_manager.get_user_data(ADMIN_ID)
                    admin_locale = user_data.get("locale", "ru")
                    set_locale(admin_locale)

                    ticket = ticket_service.get_ticket(ticket_info['id'])
                    if ticket:
                        text = format_ticket_card(ticket)
                        text = f"⏰ {_('alerts.ticket_auto_closed', ticket_id=ticket.id, hours=AUTO_CLOSE_AFTER_HOURS)}\n\n{text}"

                        # Add button to view ticket
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton(_("buttons.back"), callback_data="admin_inbox")]
                        ])

                        await alert_service._bot.send_message(
                            chat_id=ADMIN_ID,
                            text=text,
                            reply_markup=keyboard
                        )

                        logger.info(f"Sent auto-close ticket card to admin for {ticket_info['id']}")

                except Exception as e:
                    logger.error(
                        f"Failed to send auto-close ticket card to admin for {ticket_info['id']}: {e}"
                    )

                # Send notification to user
                try:
                    # Load user's locale
                    user_data = data_manager.get_user_data(ticket_info['user_id'])
                    user_locale = user_data.get("locale", "ru")

                    set_locale(user_locale)

                    user_message = _(
                        "messages.ticket_auto_closed_user",
                        ticket_id=ticket_info['id'],
                        hours=AUTO_CLOSE_AFTER_HOURS
                    )

                    await alert_service._bot.send_message(
                        chat_id=ticket_info['user_id'],
                        text=user_message
                    )

                    logger.info(f"Sent auto-close notification to user {ticket_info['user_id']}")

                except Exception as e:
                    logger.error(
                        f"Failed to send auto-close notification to user {ticket_info['user_id']}: {e}"
                    )
        else:
            logger.debug("No inactive tickets to auto-close")

    except Exception as e:
        logger.error(f"Error in auto_close_inactive_tickets: {e}", exc_info=True)
