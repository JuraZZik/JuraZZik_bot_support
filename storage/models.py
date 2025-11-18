from datetime import datetime
from typing import List, Optional


class Message:
    def __init__(self, sender: str, text: Optional[str], at: datetime):
        self.sender = sender
        self.text = text
        self.at = at

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "text": self.text,
            "at": self.at.isoformat(),
        }

    @staticmethod
    def from_dict(data: dict) -> "Message":
        return Message(
            sender=data["sender"],
            text=data.get("text"),
            at=datetime.fromisoformat(data["at"]),
        )


class Ticket:
    def __init__(
        self,
        ticket_id: str,
        user_id: int,
        created_at: datetime,
        status: str,
        messages: List[Message],
        assigned: Optional[int] = None,
        last_actor: Optional[str] = None,
        last_activity_at: Optional[datetime] = None,
        first_response_at: Optional[datetime] = None,
        rated: bool = False,
        rating: Optional[int] = None,
        feedback_invited: bool = False,
        review_received: bool = False,
        suggestion_received: bool = False,
        username: Optional[str] = None,
    ):
        self.id = ticket_id
        self.user_id = user_id
        self.created_at = created_at
        self.status = status
        self.messages = messages
        self.assigned = assigned
        self.last_actor = last_actor
        self.last_activity_at = last_activity_at
        self.first_response_at = first_response_at
        self.rated = rated
        self.rating = rating
        self.feedback_invited = feedback_invited
        self.review_received = review_received
        self.suggestion_received = suggestion_received
        self.username = username

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "messages": [m.to_dict() for m in self.messages],
            "assigned": self.assigned,
            "last_actor": self.last_actor,
            "last_activity_at": self.last_activity_at.isoformat()
            if self.last_activity_at
            else None,
            "first_response_at": self.first_response_at.isoformat()
            if self.first_response_at
            else None,
            "rated": self.rated,
            "rating": self.rating,
            "feedback_invited": self.feedback_invited,
            "review_received": self.review_received,
            "suggestion_received": self.suggestion_received,
            "username": self.username,
        }

    @staticmethod
    def from_dict(data: dict) -> "Ticket":
        return Ticket(
            ticket_id=data["id"],
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=data["status"],
            messages=[Message.from_dict(m) for m in data["messages"]],
            assigned=data.get("assigned"),
            last_actor=data.get("last_actor"),
            last_activity_at=datetime.fromisoformat(data["last_activity_at"])
            if data.get("last_activity_at")
            else None,
            first_response_at=datetime.fromisoformat(data["first_response_at"])
            if data.get("first_response_at")
            else None,
            rated=data.get("rated", False),
            rating=data.get("rating"),
            feedback_invited=data.get("feedback_invited", False),
            review_received=data.get("review_received", False),
            suggestion_received=data.get("suggestion_received", False),
            username=data.get("username"),
        )
