#!/usr/bin/env python3
"""
Text formatting utilities for tickets and messages

Handles formatting of ticket cards, previews, and message history
with proper localization and timezone conversion.
"""

from datetime import datetime
import math
import pytz

from config import TIMEZONE, TICKET_HISTORY_LIMIT, ADMIN_ID, DEFAULT_LOCALE, AUTO_CLOSE_AFTER_HOURS
from locales import get_text
from utils.locale_helper import get_admin_language
from storage.data_manager import data_manager


def format_ticket_brief(ticket) -> str:
    """
    Brief ticket preview for list (single line)

    Args:
        ticket: Ticket object

    Returns:
        Formatted brief ticket info
    """
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
            # Handle Message object (has 'text' attribute)
            if hasattr(first_msg, "text"):
                msg_preview = (first_msg.text[:30] + "...") if first_msg.text else "[empty]"
            # Handle dict format
            elif isinstance(first_msg, dict):
                msg_preview = (first_msg.get("text", "")[:30] + "...") if first_msg.get("text") else "[empty]"
            else:
                msg_preview = str(first_msg)[:30] + "..."
        else:
            msg_preview = "[no messages]"
    except Exception:
        msg_preview = "[error reading message]"

    return f"{status_emoji} {ticket.id} | {username} | {msg_preview}"


def _get_local_time(timestamp) -> str:
    """
    Convert UTC timestamp to local timezone and return HH:MM format

    Args:
        timestamp: datetime object (can be aware or naive)

    Returns:
        Time string in HH:MM format
    """
    if not isinstance(timestamp, datetime):
        return "00:00"

    try:
        tz = pytz.timezone(TIMEZONE)
        # Make timezone-aware if naive
        if timestamp.tzinfo is None:
            timestamp = pytz.UTC.localize(timestamp)
        # Convert to local timezone
        local_time = timestamp.astimezone(tz)
        return local_time.strftime("%H:%M")
    except Exception:
        try:
            return timestamp.strftime("%H:%M")
        except Exception:
            return "00:00"


def format_ticket_card(ticket) -> str:
    """
    Full ticket card with message history
    Admin sees this in their language

    Args:
        ticket: Ticket object

    Returns:
        Formatted ticket card text
    """
    # Get admin's language for displaying the card
    admin_lang = get_admin_language()

    # Status names in admin's language
    status_names = {
        "new": get_text("status_names.new", lang=admin_lang),
        "working": get_text("status_names.working", lang=admin_lang),
        "done": get_text("status_names.done", lang=admin_lang),
    }

    if ticket.username:
        username = f"@{ticket.username} (ID: {ticket.user_id})"
    else:
        username = f"ID: {ticket.user_id}"

    status = status_names.get(ticket.status, ticket.status)
    created_str = ticket.created_at.strftime("%d.%m.%Y %H:%M")

    lines = [
        f"🎫 Ticket: {ticket.id}",
        f"👤 {get_text('ui.from_label', lang=admin_lang)}: {username}",
        f"📊 {get_text('ui.status_label', lang=admin_lang)}: {status}",
        f"📅 {get_text('ui.created_label', lang=admin_lang)}: {created_str}",
    ]

    # ---------- чей ход ----------
    last_actor = getattr(ticket, "last_actor", None)
    if last_actor == "user":
        # Пользователь писал последним → ход за поддержкой
        turn_line = get_text("ui.turn_support", lang=admin_lang)
    elif last_actor == "support":
        # Поддержка писала последней → ход за пользователем
        turn_line = get_text("ui.turn_user", lang=admin_lang)
    else:
        turn_line = get_text("ui.turn_unknown", lang=admin_lang)

    lines.append(turn_line)

    # ---------- авто‑закрытие ----------
    # Показываем только если тикет ещё открыт и последний ход был за поддержкой
    if ticket.status in ("new", "working") and last_actor == "support":
        try:
            tz = pytz.timezone(TIMEZONE)
        except Exception:
            tz = pytz.UTC

        # now в нужной TZ (aware)
        now = datetime.now(tz)

        # last_activity: берём last_activity_at или created_at
        last_activity = getattr(ticket, "last_activity_at", None) or ticket.created_at

        # Приводим last_activity к той же TZ, делая aware при необходимости
        try:
            if last_activity.tzinfo is None:
                # считаем, что локальное сохранённое время уже в TIMEZONE
                last_activity = tz.localize(last_activity)
            else:
                last_activity = last_activity.astimezone(tz)
        except Exception:
            # В крайнем случае считаем, что активности не было
            last_activity = now

        hours_passed = (now - last_activity).total_seconds() / 3600
        hours_left = AUTO_CLOSE_AFTER_HOURS - hours_passed

        if hours_left <= 0:
            auto_close_line = get_text("ui.auto_close_overdue", lang=admin_lang)
        else:
            hours_left_ceil = math.ceil(hours_left)
            auto_close_line = get_text(
                "ui.auto_close_expected",
                lang=admin_lang,
                hours=hours_left_ceil,
            )
        lines.append(auto_close_line)

    # Add rating if present
    if hasattr(ticket, "rating") and ticket.rating:
        rating_texts = {
            "excellent": get_text("rating.excellent", lang=admin_lang),
            "good": get_text("rating.good", lang=admin_lang),
            "ok": get_text("rating.ok", lang=admin_lang),
        }
        rating_display = rating_texts.get(ticket.rating, ticket.rating)
        lines.append(f"⭐ {get_text('ui.rating_label', lang=admin_lang)}: {rating_display}")

    lines.extend(["", f"📝 {get_text('ui.history_label', lang=admin_lang)}:", ""])

    # Add message history
    if ticket.messages:
        # Limit messages shown (newest first or all depending on config)
        messages_to_show = (
            ticket.messages[-TICKET_HISTORY_LIMIT:]
            if TICKET_HISTORY_LIMIT > 0
            else ticket.messages
        )

        for msg in messages_to_show:
            try:
                # Handle Message object
                if hasattr(msg, "sender"):
                    sender_label = (
                        f"👤 {get_text('ui.user_label', lang=admin_lang)}"
                        if msg.sender == "user"
                        else f"🛠 {get_text('ui.support_label', lang=admin_lang)}"
                    )
                    # Use 'at' field instead of 'timestamp'
                    timestamp = msg.at if hasattr(msg, "at") else datetime.now()
                    time_str = _get_local_time(timestamp)
                    text = msg.text if hasattr(msg, "text") else str(msg)

                    lines.append(f"{sender_label} [{time_str}]:")
                    lines.append(f"{text}")
                    lines.append("")
                # Handle dict format
                elif isinstance(msg, dict):
                    sender_label = (
                        f"👤 {get_text('ui.user_label', lang=admin_lang)}"
                        if msg.get("sender") == "user"
                        else f"🛠 {get_text('ui.support_label', lang=admin_lang)}"
                    )
                    timestamp = msg.get("at", datetime.now())
                    time_str = _get_local_time(timestamp)
                    text = msg.get("text", "")

                    lines.append(f"{sender_label} [{time_str}]:")
                    lines.append(f"{text}")
                    lines.append("")
                else:
                    lines.append(f"• {str(msg)}")
                    lines.append("")
            except Exception as e:
                lines.append(f"• [Error displaying message: {e}]")
                lines.append("")
    else:
        lines.append(get_text("ui.no_messages", lang=admin_lang))

    return "\n".join(lines)


def format_ticket_preview(ticket) -> str:
    """
    Ticket preview for inbox list (multi-line)
    Admin sees this in their language

    Args:
        ticket: Ticket object

    Returns:
        Formatted ticket preview
    """
    admin_lang = get_admin_language()

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
            # Handle Message object
            if hasattr(first_msg, "text"):
                msg_preview = first_msg.text[:100] if first_msg.text else "[empty]"
            # Handle dict format
            elif isinstance(first_msg, dict):
                msg_preview = first_msg.get("text", "")[:100] if first_msg.get("text") else "[empty]"
            else:
                msg_preview = str(first_msg)[:100]
        else:
            msg_preview = get_text("ui.no_messages", lang=admin_lang)
    except Exception:
        msg_preview = "[error reading message]"

    # Индикатор "чей ход" в превью
    last_actor = getattr(ticket, "last_actor", None)
    if last_actor == "user":
        # пользователь писал последним → ход за поддержкой
        turn_emoji = " 🛠"
    elif last_actor == "support":
        # поддержка писала последней → ход за пользователем
        turn_emoji = " 👤"
    else:
        turn_emoji = ""

    return (
        f"{status_emoji} {ticket.id}{turn_emoji}\n"
        f"👤 {username}\n"
        f"📅 {created_str}\n"
        f"💬 {msg_preview}..."
    )
