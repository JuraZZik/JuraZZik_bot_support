import os
import re
import logging
from typing import List, Tuple, Optional

from config import (
    BANNED_FILE,
    BAN_DEFAULT_REASON,
    NAME_LINK_PATTERN,
    BAN_ON_NAME_LINK,
)

logger = logging.getLogger(__name__)


class BanManager:
    """Manage banned users stored in a simple text file."""

    def __init__(self) -> None:
        self.banned: dict[int, str] = self._load_banned()

    def _load_banned(self) -> dict[int, str]:
        """Load banned users list from BANNED_FILE."""
        banned: dict[int, str] = {}
        if not os.path.exists(BANNED_FILE):
            logger.info(
                "Banned file not found: %s (starting with empty list)",
                BANNED_FILE,
            )
            return banned

        try:
            with open(BANNED_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split("|", 1)
                    user_id_raw = parts[0].strip()
                    if not user_id_raw.isdigit():
                        logger.warning(
                            "Invalid user_id in banned file: %r",
                            user_id_raw,
                        )
                        continue

                    uid = int(user_id_raw)
                    reason = (
                        parts[1].strip()
                        if len(parts) > 1
                        else BAN_DEFAULT_REASON
                    )
                    banned[uid] = reason

            logger.info(
                "Loaded %d banned users from %s",
                len(banned),
                BANNED_FILE,
            )
        except Exception as e:
            logger.error(
                "Error loading banned file %s: %s",
                BANNED_FILE,
                e,
                exc_info=True,
            )

        return banned

    def _save_banned(self) -> None:
        """Save banned users list to BANNED_FILE."""
        try:
            dir_name = os.path.dirname(BANNED_FILE) or "."
            os.makedirs(dir_name, exist_ok=True)

            with open(BANNED_FILE, "w", encoding="utf-8") as f:
                for uid, reason in self.banned.items():
                    f.write(f"{uid}|{reason}\n")

            logger.debug("Banned users list saved to %s", BANNED_FILE)
        except Exception as e:
            logger.error(
                "Error saving banned file %s: %s",
                BANNED_FILE,
                e,
                exc_info=True,
            )

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned."""
        return user_id in self.banned

    def get_ban_reason(self, user_id: int) -> Optional[str]:
        """Get ban reason for given user_id."""
        return self.banned.get(user_id)

    def ban_user(self, user_id: int, reason: str = BAN_DEFAULT_REASON) -> None:
        """Ban user with optional reason."""
        self.banned[user_id] = reason
        self._save_banned()
        logger.info("User %s banned: %s", user_id, reason)

    def unban_user(self, user_id: int) -> None:
        """Unban user if present."""
        if user_id in self.banned:
            del self.banned[user_id]
            self._save_banned()
            logger.info("User %s unbanned", user_id)
        else:
            logger.warning(
                "Attempted to unban non-existing banned user %s",
                user_id,
            )

    def get_banned_list(self) -> List[Tuple[int, str]]:
        """Get list of banned users as (user_id, reason)."""
        return list(self.banned.items())

    def check_name_for_link(self, name: str) -> bool:
        """
        Check display name for links according to NAME_LINK_PATTERN.

        Uses BAN_ON_NAME_LINK flag to enable/disable this check.
        """
        if not BAN_ON_NAME_LINK or not name:
            return False
        pattern = re.compile(NAME_LINK_PATTERN, re.IGNORECASE)
        return bool(pattern.search(name))


# Global instance
ban_manager = BanManager()
