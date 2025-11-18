"""
State constants for user/admin flows.
"""

# User conversation states
STATE_AWAITING_QUESTION = "awaiting_question"
STATE_AWAITING_SUGGESTION = "awaiting_suggestion"
STATE_AWAITING_REVIEW = "awaiting_review"
STATE_AWAITING_REPLY = "awaiting_reply"

# Admin flows via callbacks
STATE_SEARCH_TICKET_INPUT = "search_ticket_input"
STATE_AWAITING_BAN_USER_ID = "awaiting_ban_user_id"
STATE_AWAITING_BAN_REASON = "awaiting_ban_reason"
STATE_AWAITING_UNBAN_USER_ID = "awaiting_unban_user_id"
