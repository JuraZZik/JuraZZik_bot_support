import logging
from datetime import datetime
from typing import Optional, List

from storage.models import Ticket, Message
from storage.data_manager import data_manager
from config import TIMEZONE

logger = logging.getLogger(__name__)


class TicketService:
    def generate_ticket_id(self) -> str:
        """Generate unique ticket ID."""
        now = datetime.now(TIMEZONE)
        date_part = now.strftime("%Y%m%d")

        prefix = f"T-{date_part}-"
        existing = [
            t.id
            for t in data_manager.get_all_tickets()
            if t.id.startswith(prefix)
        ]

        if not existing:
            num = 1
        else:
            nums = [int(tid.split("-")[-1]) for tid in existing]
            num = max(nums) + 1

        return f"{prefix}{num:04d}"

    def create_ticket(
        self,
        user_id: int,
        initial_message: str,
        username: Optional[str] = None,
    ) -> Ticket:
        """Create new ticket."""
        ticket_id = self.generate_ticket_id()
        now = datetime.now(TIMEZONE)

        message = Message(sender="user", text=initial_message, at=now)

        ticket = Ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            created_at=now,
            status="new",
            messages=[message],
            last_activity_at=now,
            last_actor="user",
            username=username,
        )

        data_manager.create_ticket(ticket)
        logger.info("Created ticket %s for user %s", ticket_id, user_id)

        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get ticket by ID."""
        logger.debug("Getting ticket: %s", ticket_id)
        return data_manager.get_ticket(ticket_id)

    def add_message(
        self,
        ticket_id: str,
        sender: str,
        text: Optional[str],
        admin_id: Optional[int] = None,
    ) -> Optional[Ticket]:
        """Add message to ticket and update last_actor."""
        ticket = data_manager.get_ticket(ticket_id)
        if not ticket:
            logger.error("Ticket %s not found", ticket_id)
            return None

        now = datetime.now(TIMEZONE)
        message = Message(sender=sender, text=text, at=now)
        ticket.messages.append(message)
        ticket.last_activity_at = now
        ticket.last_actor = sender

        # If admin replies for first time, set response time and assign ticket
        if sender == "support" and ticket.first_response_at is None:
            ticket.first_response_at = now
            if admin_id:
                ticket.assigned = admin_id

        data_manager.update_ticket(ticket)
        logger.info(
            "Added %s message to ticket %s, last_actor=%s",
            sender,
            ticket_id,
            sender,
        )

        return ticket

    def take_ticket(self, ticket_id: str, admin_id: int) -> Optional[Ticket]:
        """Take ticket in progress."""
        ticket = data_manager.get_ticket(ticket_id)
        if not ticket:
            logger.error("Ticket %s not found", ticket_id)
            return None

        ticket.status = "working"
        ticket.assigned = admin_id
        ticket.last_activity_at = datetime.now(TIMEZONE)

        data_manager.update_ticket(ticket)
        logger.info("Ticket %s taken by admin %s", ticket_id, admin_id)

        return ticket

    def close_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Close ticket."""
        ticket = data_manager.get_ticket(ticket_id)
        if not ticket:
            logger.error("Ticket %s not found", ticket_id)
            return None

        ticket.status = "done"
        ticket.last_activity_at = datetime.now(TIMEZONE)

        data_manager.update_ticket(ticket)
        logger.info("Ticket %s closed", ticket_id)

        return ticket

    def rate_ticket(self, ticket_id: str, rating: int) -> Optional[Ticket]:
        """Rate ticket by user."""
        ticket = data_manager.get_ticket(ticket_id)
        if not ticket:
            logger.error("Ticket %s not found", ticket_id)
            return None

        ticket.rated = True
        ticket.rating = rating

        data_manager.update_ticket(ticket)
        logger.info("Ticket %s rated: %s", ticket_id, rating)

        return ticket

    def get_active_tickets(self) -> List[Ticket]:
        """Get all active tickets (new or working)."""
        return [
            t
            for t in data_manager.get_all_tickets()
            if t.status in ["new", "working"]
        ]

    def get_user_active_ticket(self, user_id: int) -> Optional[Ticket]:
        """Get user's most recent active ticket (new or working status)."""
        tickets = [
            t
            for t in data_manager.get_all_tickets()
            if t.user_id == user_id and t.status in ["new", "working"]
        ]

        if not tickets:
            return None

        most_recent = max(tickets, key=lambda t: t.created_at)
        logger.debug(
            "User %s has %s active ticket(s), returning: %s",
            user_id,
            len(tickets),
            most_recent.id,
        )

        return most_recent

    def clear_active_tickets(self) -> int:
        """Close all active tickets."""
        now = datetime.now(TIMEZONE)
        count = 0
        for ticket in self.get_active_tickets():
            ticket.status = "done"
            ticket.last_activity_at = now
            data_manager.update_ticket(ticket)
            count += 1

        logger.info("Cleared %s active tickets", count)
        return count


# Global instance
ticket_service = TicketService()
