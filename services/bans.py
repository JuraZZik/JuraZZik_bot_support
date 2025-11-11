import os
import re
import logging
from typing import List, Tuple, Optional
from config import BANNED_FILE, BAN_DEFAULT_REASON, NAME_LINK_PATTERN, BAN_ON_NAME_LINK

logger = logging.getLogger(__name__)

class BanManager:
    def __init__(self):
        self.banned = self._load_banned()

    def _load_banned(self) -> dict:
        """Load banned users list"""
        banned = {}
        if os.path.exists(BANNED_FILE):
            try:
                with open(BANNED_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split("|", 1)
                        uid = int(parts[0].strip())
                        reason = parts[1].strip() if len(parts) > 1 else BAN_DEFAULT_REASON
                        banned[uid] = reason
            except Exception as e:
                logger.error(f"Error loading banned file: {e}", exc_info=True)
        return banned

    def _save_banned(self):
        """Save banned users list"""
        try:
            with open(BANNED_FILE, "w", encoding="utf-8") as f:
                for uid, reason in self.banned.items():
                    f.write(f"{uid}|{reason}\n")
        except Exception as e:
            logger.error(f"Error saving banned file: {e}", exc_info=True)

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        return user_id in self.banned

    def get_ban_reason(self, user_id: int) -> Optional[str]:
        """Get ban reason"""
        return self.banned.get(user_id)

    def ban_user(self, user_id: int, reason: str = BAN_DEFAULT_REASON):
        """Ban user"""
        self.banned[user_id] = reason
        self._save_banned()
        logger.info(f"User {user_id} banned: {reason}")

    def unban_user(self, user_id: int):
        """Unban user"""
        if user_id in self.banned:
            del self.banned[user_id]
            self._save_banned()
            logger.info(f"User {user_id} unbanned")

    def get_banned_list(self) -> List[Tuple[int, str]]:
        """Get list of banned users (user_id, reason)"""
        return [(uid, reason) for uid, reason in self.banned.items()]

    def check_name_for_link(self, name: str) -> bool:
        """Check name for links"""
        if not BAN_ON_NAME_LINK or not name:
            return False
        pattern = re.compile(NAME_LINK_PATTERN, re.IGNORECASE)
        return bool(pattern.search(name))

# Global instance
ban_manager = BanManager()
