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

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing user feedback (suggestions and reviews)"""

    def __init__(self):
        # Storage: (user_id, type) -> datetime for cooldown tracking
        self.last_feedback = {}
        # Storage: feedback_id -> feedback_data
        self.feedbacks = {}

    def check_cooldown(self, user_id: int, feedback_type: str, user_lang: str = None):
        """Check cooldown for feedback submission with proper localization

        Args:
            user_id: User ID
            feedback_type: Type of feedback (suggestion or review)
            user_lang: User language for localized error message

        Returns:
            Tuple (can_send: bool, error_message: str or None)
        """
        user_lang = user_lang or DEFAULT_LOCALE

        # Return True if cooldown is disabled
        if not FEEDBACK_COOLDOWN_ENABLED:
            return True, None

        # Get last feedback timestamp for this user and type
        last_time = self.last_feedback.get((user_id, feedback_type))
        if not last_time:
            return True, None

        # Calculate elapsed time in seconds
        elapsed = (datetime.now(TIMEZONE) - last_time).total_seconds()
        need = FEEDBACK_COOLDOWN_HOURS * 3600

        # Check if cooldown period has passed
        if elapsed >= need:
            return True, None

        # Calculate remaining hours
        remaining = int((need - elapsed + 3599) // 3600)

        # Build localization key
        key = f"messages.{feedback_type}_cooldown"

        # Get localized error message
        message = get_text(
            key,
            lang=user_lang,
            hours=remaining
        )

        return False, message

    def update_last_feedback(self, user_id: int, feedback_type: str):
        """Update last feedback timestamp for user to track cooldown

        Args:
            user_id: User ID
            feedback_type: Type of feedback (suggestion or review)
        """
        self.last_feedback[(user_id, feedback_type)] = datetime.now(TIMEZONE)
        logger.info(f"Updated {feedback_type} timestamp for user {user_id}")

    def create_feedback(self, user_id: int, feedback_type: str, text: str) -> str:
        """Create new feedback record

        Args:
            user_id: User ID
            feedback_type: Type (suggestion or review)
            text: Feedback text

        Returns:
            Feedback ID (format: type_randomhex)
        """
        # Generate unique feedback ID with format: sug_12345abc or rev_87654def
        feedback_id = f"{feedback_type[:3]}_{uuid.uuid4().hex[:8]}"

        # Store feedback data
        self.feedbacks[feedback_id] = {
            "user_id": user_id,
            "type": feedback_type,
            "text": text,
            "thanked": False,  # Admin hasn't sent thank you yet
            "message_id": None,  # Telegram message ID for editing
            "created_at": datetime.now(TIMEZONE)
        }

        logger.info(f"Created feedback {feedback_id} from user {user_id}")
        return feedback_id

    def get_feedback(self, feedback_id: str) -> dict:
        """Get feedback by ID

        Args:
            feedback_id: Feedback ID

        Returns:
            Feedback data dict or None if not found
        """
        feedback = self.feedbacks.get(feedback_id)
        if feedback:
            logger.debug(f"Retrieved feedback {feedback_id}")
        else:
            logger.warning(f"Feedback {feedback_id} not found")
        return feedback

    def thank_feedback(self, feedback_id: str) -> dict:
        """Mark feedback as thanked by admin and return feedback data

        Args:
            feedback_id: Feedback ID

        Returns:
            Feedback data dict or None if not found
        """
        # Get feedback from storage
        feedback = self.feedbacks.get(feedback_id)
        if feedback:
            # Mark as thanked by admin
            feedback["thanked"] = True
            logger.info(f"Feedback {feedback_id} marked as thanked")
        return feedback

    def set_message_id(self, feedback_id: str, message_id: int):
        """Save Telegram message ID for feedback card (used for editing)

        Args:
            feedback_id: Feedback ID
            message_id: Telegram message ID
        """
        # Store message ID for later editing
        if feedback_id in self.feedbacks:
            self.feedbacks[feedback_id]["message_id"] = message_id
            logger.debug(f"Set message_id for feedback {feedback_id}: {message_id}")


# Global instance - instantiate after class definition to avoid circular imports
feedback_service = FeedbackService()
