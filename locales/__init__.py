import json
import os
from typing import Dict, Any, Optional

# Global state for current locale and locales data
_current_locale = None
# Dictionary to store loaded locale data: {locale_code: {key: value}}
_locales_data: Dict[str, Dict[str, Any]] = {}
# Dictionary to store user-specific locale preferences: {user_id: locale_code}
_user_locales: Dict[int, str] = {}


def load_locales():
    """Load all locale files from locales directory"""
    global _locales_data

    locales_dir = os.path.dirname(__file__)

    # Load both Russian and English locale files
    for locale_file in ["ru.json", "en.json"]:
        file_path = os.path.join(locales_dir, locale_file)
        locale_code = locale_file.replace(".json", "")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _locales_data[locale_code] = json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Locale file not found: {file_path}")
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing {locale_file}: {e}")


def set_locale(locale_code: str) -> bool:
    """
    Set global locale for all translations
    
    Args:
        locale_code: Language code (ru, en)
    
    Returns:
        True if locale set successfully, False otherwise
    """
    global _current_locale

    if locale_code not in _locales_data:
        print(f"⚠️ Locale '{locale_code}' not found. Available: {list(_locales_data.keys())}")
        return False

    _current_locale = locale_code
    return True


def set_user_locale(user_id: int, locale_code: str) -> bool:
    """
    Set locale for specific user
    
    Args:
        user_id: Telegram user ID
        locale_code: Language code (ru, en)
    
    Returns:
        True if locale set successfully, False otherwise
    """
    if locale_code not in _locales_data:
        print(f"⚠️ Locale '{locale_code}' not found. Available: {list(_locales_data.keys())}")
        return False

    # Save in memory
    _user_locales[user_id] = locale_code

    # FIX: Also save in data_manager for persistence!
    try:
        from storage.data_manager import data_manager
        data_manager.update_user_data(user_id, {"locale": locale_code})
    except ImportError:
        print(f"⚠️ Could not import data_manager to persist locale")

    return True


def get_user_locale(user_id: int) -> Optional[str]:
    """
    Get locale for specific user
    
    Args:
        user_id: Telegram user ID
    
    Returns:
        User's locale code or global locale if not set
    """
    # First check in-memory cache
    if user_id in _user_locales:
        return _user_locales[user_id]

    # Then check data_manager for persistence
    try:
        from storage.data_manager import data_manager
        user_data = data_manager.get_user_data(user_id)
        locale = user_data.get("locale")
        if locale:
            # Cache in memory
            _user_locales[user_id] = locale
            return locale
    except ImportError:
        pass

    # If nothing found, use global locale
    return _current_locale


def get_locale() -> str:
    """
    Get current global locale
    
    Returns:
        Current global locale code
    """
    return _current_locale


def get_text(key: str, lang: Optional[str] = None, locale: Optional[str] = None, **kwargs) -> str:
    """
    Get translated text from current locale
    
    Priority order:
    1. Explicit locale parameter
    2. User-specific locale (if user_id in kwargs)
    3. Global locale
    
    Args:
        key: Dot-separated translation key (e.g., "messages.welcome", "buttons.close")
        lang: Language code (backward compatibility alias for locale)
        locale: Explicit locale code to override all defaults
        **kwargs: Format parameters for string formatting
            - user_id: To get user-specific locale
            - Other parameters: Used for .format() on the translated string
    
    Returns:
        Translated text with applied formatting, or key if translation not found
    
    Example:
        get_text("messages.welcome", user_id=123)
        get_text("messages.ticket_closed", ticket_id="ABC123")
        get_text("admin.new_ticket", locale="ru", user_id=456)
    """
    current_locale = None
    try:
        # Backward compatibility: lang is alias for locale
        if lang and not locale:
            locale = lang

        # Extract user_id from kwargs for user-specific locale lookup
        user_id = kwargs.get("user_id")

        # Determine which locale to use (priority: explicit > user > global)
        if locale:
            current_locale = locale
        elif user_id is not None:
            current_locale = get_user_locale(user_id)
        else:
            current_locale = _current_locale

        if not current_locale:
            print(f"❌ No locale set (key: {key})")
            return key

        # Navigate through nested dictionary using dot notation
        # e.g., "messages.welcome" -> _locales_data[locale]["messages"]["welcome"]
        keys = key.split(".")
        value = _locales_data[current_locale]

        for k in keys:
            value = value[k]

        # Format string with provided parameters
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as format_error:
                print(f"⚠️ Format parameter missing in key '{key}': {format_error}")
                # Return unformatted value instead of key
                return value
        
        return value

    except (KeyError, AttributeError) as e:
        error_locale = current_locale if current_locale else "unknown"
        print(f"❌ Translation key not found: {key} (locale: {error_locale}, error: {e})")
        return key


# Alias for gettext-style usage (more concise)
# Usage: _("messages.welcome") instead of get_text("messages.welcome")
_ = get_text


# Initialize locales on module import
load_locales()
