import re
from typing import Optional
from config import NAME_LINK_PATTERN, BAN_ON_NAME_LINK


def validate_ticket_id(ticket_id: str) -> bool:
    """Validate ticket ID format"""
    pattern = r'^T-\d{8}-\d{4}$'
    return bool(re.match(pattern, ticket_id))


def validate_user_id(user_id_str: str) -> Optional[int]:
    """Validate and parse user ID"""
    try:
        user_id = int(user_id_str.strip())
        if user_id > 0:
            return user_id
    except ValueError:
        pass
    return None


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Clean and truncate text"""
    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text


def is_valid_username(username: str) -> bool:
    """Check username validity"""
    if not username:
        return False
    pattern = r'^[a-zA-Z0-9_]{5,32}$'
    return bool(re.match(pattern, username))


def has_link_in_name(name: str) -> bool:
    """
    Check for links in username.
    Uses NAME_LINK_PATTERN from config.

    Args:
        name: Username to check

    Returns:
        True if link found, False otherwise
    """
    if not name:
        return False

    # Use regex from config
    return bool(re.search(NAME_LINK_PATTERN, name, re.IGNORECASE))


def should_ban_for_name_link(name: str) -> bool:
    """
    Check if user should be banned for link in name.
    Considers BAN_ON_NAME_LINK setting from config.

    Args:
        name: Username to check

    Returns:
        True if should ban, False otherwise
    """
    if not BAN_ON_NAME_LINK:
        return False

    return has_link_in_name(name)
