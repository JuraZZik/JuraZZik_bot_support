import logging
import uuid
from datetime import datetime
from config import (
    TIMEZONE,
    FEEDBACK_COOLDOWN_ENABLED,
    FEEDBACK_COOLDOWN_HOURS,
)
from locales import _

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self):
        self.last_feedback = {}  # (user_id, type) -> datetime
        self.feedbacks = {}

    def check_cooldown(self, user_id: int, feedback_type: str):
        """Check cooldown"""
        if not FEEDBACK_COOLDOWN_ENABLED:
            return True, None

        last_time = self.last_feedback.get((user_id, feedback_type))
        if not last_time:
            return True, None

        # FIXED: Use TIMEZONE directly
        elapsed = (datetime.now(TIMEZONE) - last_time).total_seconds()
        need = FEEDBACK_COOLDOWN_HOURS * 3600

        if elapsed >= need:
            return True, None

        remaining = int((need - elapsed + 3599) // 3600)
        feedback_name = "suggestion" if feedback_type == "suggestion" else "review"
        message = (
            f"{_('alerts.time')} You already sent a {feedback_name}.\n\n"
            f"Try again in {remaining}h."
        )
        return False, message

    def update_last_feedback(self, user_id: int, feedback_type: str):
        """Update last feedback timestamp"""
        # FIXED: Use TIMEZONE directly
        self.last_feedback[(user_id, feedback_type)] = datetime.now(TIMEZONE)
        logger.info(f"Updated {feedback_type} timestamp for user {user_id}")

    def create_feedback(self, user_id: int, feedback_type: str, text: str) -> str:
        """Create new feedback/suggestion"""
        feedback_id = f"{feedback_type[:3]}_{uuid.uuid4().hex[:8]}"
        self.feedbacks[feedback_id] = {
            "user_id": user_id,
            "type": feedback_type,
            "text": text,
            "thanked": False,
            "message_id": None
        }
        logger.info(f"Created feedback {feedback_id} from user {user_id}")
        return feedback_id

    def thank_feedback(self, feedback_id: str) -> dict:
        """Mark feedback/suggestion as thanked"""
        feedback = self.feedbacks.get(feedback_id)
        if feedback:
            feedback["thanked"] = True
            logger.info(f"Feedback {feedback_id} marked as thanked")
        return feedback

    def set_message_id(self, feedback_id: str, message_id: int):
        """Save message_id for card editing"""
        if feedback_id in self.feedbacks:
            self.feedbacks[feedback_id]["message_id"] = message_id


# Global instance
feedback_service = FeedbackService()
