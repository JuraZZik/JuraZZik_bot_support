from datetime import datetime
import pytz
from config import TIMEZONE, TICKET_HISTORY_LIMIT, ADMIN_ID, DEFAULT_LOCALE
from locales import _, set_locale
from storage.data_manager import data_manager


def format_ticket_brief(ticket) -> str:
    """Brief ticket preview for list (single line)"""
    status_emoji = {
        "new": "🆕",
        "working": "⏳",
        "done": "✅"
    }.get(ticket.status, "❓")

    if ticket.username:
        username = f"@{ticket.username} (ID:{ticket.user_id})"
    else:
        username = f"ID:{ticket.user_id}"

    try:
        if ticket.messages:
            first_msg = ticket.messages[0]
            if hasattr(first_msg, 'text'):
                msg_preview = first_msg.text[:30] + "..."
            elif isinstance(first_msg, dict):
                msg_preview = first_msg.get("text", "")[:30] + "..."
            else:
                msg_preview = str(first_msg)[:30] + "..."
        else:
            msg_preview = _("ui.no_messages")
    except Exception:
        msg_preview = _("ui.no_messages")

    return f"{status_emoji} {ticket.id} | {username} | {msg_preview}"


def _get_local_time(timestamp) -> str:
    """Convert UTC timestamp to local timezone and return HH:MM format"""
    if not isinstance(timestamp, datetime):
        return "00:00"

    try:
        tz = pytz.timezone(TIMEZONE)
        if timestamp.tzinfo is None:
            timestamp = pytz.UTC.localize(timestamp)
        local_time = timestamp.astimezone(tz)
        return local_time.strftime("%H:%M")
    except Exception:
        return timestamp.strftime("%H:%M")


def format_ticket_card(ticket) -> str:
    """Full ticket card with message history"""

    # ADMIN sees in their language! (with translation)
    admin_data = data_manager.get_user_data(ADMIN_ID)
    admin_locale = admin_data.get("locale") or DEFAULT_LOCALE
    set_locale(admin_locale)

    status_names = {
        "new": _("status_names.new"),
        "working": _("status_names.working"),
        "done": _("status_names.done")
    }

    if ticket.username:
        username = f"@{ticket.username} (ID: {ticket.user_id})"
    else:
        username = f"ID: {ticket.user_id}"

    status = status_names.get(ticket.status, ticket.status)
    created_str = ticket.created_at.strftime("%d.%m.%Y %H:%M")

    lines = [
        f"🎫 Ticket: {ticket.id}",
        f"👤 {_('ui.from_label')}: {username}",
        f"📊 {_('ui.status_label')}: {status}",
        f"📅 {_('ui.created_label')}: {created_str}",
    ]

    if hasattr(ticket, 'rating') and ticket.rating:
        rating_texts = {
            "excellent": _("rating.excellent"),
            "good": _("rating.good"),
            "ok": _("rating.ok")
        }
        rating_display = rating_texts.get(ticket.rating, ticket.rating)
        lines.append(f"⭐ {_('ui.rating_label')}: {rating_display}")

    lines.extend(["", f"📝 {_('ui.history_label')}:", ""])

    if ticket.messages:
        messages_to_show = ticket.messages[-TICKET_HISTORY_LIMIT:] if TICKET_HISTORY_LIMIT > 0 else ticket.messages

        for msg in messages_to_show:
            try:
                # Handle Message object
                if hasattr(msg, 'sender'):
                    sender = f"👤 {_('ui.user_label')}" if msg.sender == "user" else f"🛠 {_('ui.support_label')}"
                    timestamp = msg.timestamp if hasattr(msg, 'timestamp') else datetime.now()
                    time_str = _get_local_time(timestamp)
                    text = msg.text if hasattr(msg, 'text') else str(msg)

                    lines.append(f"{sender} [{time_str}]:")
                    lines.append(f"{text}")
                    lines.append("")
                # Handle dict
                elif isinstance(msg, dict):
                    sender = f"👤 {_('ui.user_label')}" if msg.get("sender") == "user" else f"🛠 {_('ui.support_label')}"
                    timestamp = msg.get("timestamp", datetime.now())
                    time_str = _get_local_time(timestamp)
                    text = msg.get("text", "")

                    lines.append(f"{sender} [{time_str}]:")
                    lines.append(f"{text}")
                    lines.append("")
                else:
                    lines.append(f"• {str(msg)}")
                    lines.append("")
            except Exception as e:
                lines.append(f"• [Display error]")
                lines.append("")
    else:
        lines.append(_("ui.no_messages"))

    return "\n".join(lines)


def format_ticket_preview(ticket) -> str:
    """Ticket preview for inbox list (multi-line)"""
    status_emoji = {
        "new": "🆕",
        "working": "⏳",
        "done": "✅"
    }.get(ticket.status, "❓")

    if ticket.username:
        username = f"@{ticket.username} (ID:{ticket.user_id})"
    else:
        username = f"ID:{ticket.user_id}"

    created_str = ticket.created_at.strftime("%d.%m.%Y %H:%M")

    try:
        if ticket.messages:
            first_msg = ticket.messages[0]
            if hasattr(first_msg, 'text'):
                msg_preview = first_msg.text[:100]
            elif isinstance(first_msg, dict):
                msg_preview = first_msg.get("text", "")[:100]
            else:
                msg_preview = str(first_msg)[:100]
        else:
            msg_preview = _("ui.no_messages")
    except Exception:
        msg_preview = _("ui.no_messages")

    return (
        f"{status_emoji} {ticket.id}\n"
        f"👤 {username}\n"
        f"📅 {created_str}\n"
        f"💬 {msg_preview}...\n"
    )
