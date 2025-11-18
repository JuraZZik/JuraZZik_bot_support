import logging
import uuid
from datetime import datetime

from config import (
    TIMEZONE,
    FEEDBACK_COOLDOWN_ENABLED,
    FEEDBACK_COOLDOWN_HOURS,
    DEFAULT_LOCALE,
)
from locales import get_text
from storage.data_manager import data_manager

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing user feedback (suggestions and reviews) with persistence."""

    def check_cooldown(
        self,
        user_id: int,
        feedback_type: str,
        user_lang: str | None = None,
    ):
        """
        Check cooldown for feedback submission with proper localization.

        Args:
            user_id: User ID
            feedback_type: "suggestion" or "review"
            user_lang: User language for localized error message

        Returns:
            Tuple (can_send: bool, error_message: str | None)
        """
        user_lang = user_lang or DEFAULT_LOCALE

        if not FEEDBACK_COOLDOWN_ENABLED:
            return True, None

        last_time = data_manager.get_feedback_cooldown(user_id, feedback_type)
        if not last_time:
            return True, None

        elapsed = (datetime.now(TIMEZONE) - last_time).total_seconds()
        need = FEEDBACK_COOLDOWN_HOURS * 3600

        if elapsed >= need:
            return True, None

        remaining = int((need - elapsed + 3599) // 3600)
        key = f"messages.{feedback_type}_cooldown"
        message = get_text(key, lang=user_lang, hours=remaining)
        return False, message

    def update_last_feedback(self, user_id: int, feedback_type: str) -> None:
        """
        Update last feedback timestamp for user to track cooldown.

        Args:
            user_id: User ID
            feedback_type: "suggestion" or "review"
        """
        now = datetime.now(TIMEZONE)
        data_manager.set_feedback_cooldown(user_id, feedback_type, now)
        logger.info(
            "Updated %s cooldown timestamp for user %s at %s",
            feedback_type,
            user_id,
            now.isoformat(),
        )

    def create_feedback(self, user_id: int, feedback_type: str, text: str) -> str:
        """
        Create new feedback record and persist it.

        Args:
            user_id: User ID
            feedback_type: "suggestion" or "review"
            text: Feedback text

        Returns:
            Feedback ID (format: type_randomhex)
        """
        feedback_id = f"{feedback_type[:3]}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(TIMEZONE)

        feedback_data = {
            "user_id": user_id,
            "type": feedback_type,
            "text": text,
            "thanked": False,
            "message_id": None,
            "created_at": created_at.isoformat(),
        }

        data_manager.save_feedback(feedback_id, feedback_data)

        logger.info("Created feedback %s from user %s", feedback_id, user_id)
        return feedback_id

    def get_feedback(self, feedback_id: str) -> dict | None:
        """
        Get feedback by ID.

        Returns:
            Feedback data dict or None if not found.
        """
        feedback = data_manager.get_feedback(feedback_id)
        if feedback:
            logger.debug("Retrieved feedback %s", feedback_id)
        else:
            logger.warning("Feedback %s not found", feedback_id)
        return feedback

    def thank_feedback(self, feedback_id: str) -> dict | None:
        """
        Mark feedback as thanked by admin and return feedback data.

        Args:
            feedback_id: Feedback ID

        Returns:
            Feedback data dict or None if not found.
        """
        feedback = data_manager.get_feedback(feedback_id)
        if feedback:
            data_manager.update_feedback(feedback_id, {"thanked": True})
            feedback["thanked"] = True
            logger.info("Feedback %s marked as thanked", feedback_id)
        return feedback

    def set_message_id(self, feedback_id: str, message_id: int) -> None:
        """
        Save Telegram message ID for feedback card (used for editing).

        Args:
            feedback_id: Feedback ID
            message_id: Telegram message ID
        """
        feedback = data_manager.get_feedback(feedback_id)
        if not feedback:
            logger.warning(
                "Attempted to set message_id for non-existing feedback %s",
                feedback_id,
            )
            return

        data_manager.update_feedback(feedback_id, {"message_id": message_id})
        logger.debug(
            "Set message_id for feedback %s: %s",
            feedback_id,
            message_id,
        )


# Global instance
feedback_service = FeedbackService()
