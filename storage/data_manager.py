import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from storage.models import Ticket
from config import DATA_FILE, TIMEZONE

logger = logging.getLogger(__name__)


class DataManager:
    def __init__(self) -> None:
        # Основное хранилище
        self.data: Dict[str, dict] = {
            "tickets": {},
            "users": {},
            "feedbacks": {},           # feedback_id -> dict
            "feedback_cooldowns": {},  # user_id(str) -> {feedback_type: iso_datetime_str}
        }
        self.load()

    # ---------- low-level IO helpers ----------

    def _load_from_path(self, path: str) -> Optional[dict]:
        """Load raw JSON dict from given path or return None on error."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("Data file not found: %s", path)
        except json.JSONDecodeError as e:
            logger.error("JSON decode error in %s: %s", path, e, exc_info=True)
        except Exception as e:
            logger.error("Unexpected error reading %s: %s", path, e, exc_info=True)
        return None

    def _safe_write_json(self, path: str, payload: dict) -> None:
        """
        Safely write JSON to file:
        1) write to temp file
        2) optionally backup old file
        3) atomically replace main file
        """
        dir_name = os.path.dirname(path) or "."
        os.makedirs(dir_name, exist_ok=True)

        tmp_path = f"{path}.tmp"
        bak_path = f"{path}.bak"

        try:
            # 1) write temp
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            # 2) backup old file (best-effort)
            if os.path.exists(path):
                try:
                    if os.path.exists(bak_path):
                        os.remove(bak_path)
                    os.replace(path, bak_path)
                    logger.debug("Created backup: %s", bak_path)
                except Exception as e:
                    logger.warning(
                        "Failed to create data backup %s: %s",
                        bak_path,
                        e,
                        exc_info=True,
                    )

            # 3) atomically replace
            os.replace(tmp_path, path)
            logger.debug("Data saved to %s", path)

        except Exception as e:
            logger.error("Error in safe write to %s: %s", path, e, exc_info=True)
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    # ---------- public API ----------

    def load(self) -> None:
        """Load data from DATA_FILE, fallback to .bak on error."""
        raw = self._load_from_path(DATA_FILE)

        if raw is None:
            bak_path = f"{DATA_FILE}.bak"
            logger.warning("Trying to load data from backup: %s", bak_path)
            raw = self._load_from_path(bak_path)

        if raw is None:
            logger.error(
                "Failed to load data from main and backup, starting with empty storage"
            )
            self.data = {
                "tickets": {},
                "users": {},
                "feedbacks": {},
                "feedback_cooldowns": {},
            }
            return

        try:
            # users
            self.data["users"] = raw.get("users", {})

            # tickets
            tickets_raw = raw.get("tickets", {})
            self.data["tickets"] = {
                tid: Ticket.from_dict(tdata) for tid, tdata in tickets_raw.items()
            }

            # feedbacks (in plain dict form)
            self.data["feedbacks"] = raw.get("feedbacks", {})

            # cooldowns: user_id(str) -> {feedback_type: iso_datetime_str}
            self.data["feedback_cooldowns"] = raw.get("feedback_cooldowns", {})

            logger.info(
                "Loaded %d tickets, %d users, %d feedbacks",
                len(self.data["tickets"]),
                len(self.data["users"]),
                len(self.data["feedbacks"]),
            )
        except Exception as e:
            logger.error("Error parsing loaded data: %s", e, exc_info=True)
            self.data = {
                "tickets": {},
                "users": {},
                "feedbacks": {},
                "feedback_cooldowns": {},
            }

    def save(self) -> None:
        """Save data to DATA_FILE safely."""
        try:
            tickets_dict = {
                tid: t.to_dict() for tid, t in self.data["tickets"].items()
            }
            output = {
                "tickets": tickets_dict,
                "users": self.data["users"],
                "feedbacks": self.data.get("feedbacks", {}),
                "feedback_cooldowns": self.data.get("feedback_cooldowns", {}),
            }
            self._safe_write_json(DATA_FILE, output)
        except Exception as e:
            logger.error("Error saving data: %s", e, exc_info=True)

    # ---------- tickets API ----------

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get ticket by ID."""
        return self.data["tickets"].get(ticket_id)

    def create_ticket(self, ticket: Ticket) -> None:
        """Create new ticket."""
        self.data["tickets"][ticket.id] = ticket
        self.save()

    def update_ticket(self, ticket: Ticket) -> None:
        """Update existing ticket."""
        if ticket.id in self.data["tickets"]:
            self.data["tickets"][ticket.id] = ticket
            self.save()
        else:
            logger.warning("Attempted to update non-existing ticket %s", ticket.id)

    def delete_ticket(self, ticket_id: str) -> None:
        """Delete ticket."""
        if ticket_id in self.data["tickets"]:
            del self.data["tickets"][ticket_id]
            self.save()
        else:
            logger.warning("Attempted to delete non-existing ticket %s", ticket_id)

    def get_all_tickets(self) -> List[Ticket]:
        """Get all tickets."""
        return list(self.data["tickets"].values())

    def get_tickets_by_status(self, status: str) -> List[Ticket]:
        """Get tickets by status."""
        return [t for t in self.data["tickets"].values() if t.status == status]

    # ---------- users API ----------

    def get_user_data(self, user_id: int) -> dict:
        """Get user data; creates default record if not present."""
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {
                "last_review": None,
                "last_suggestion": None,
                "thanked": False,
            }
            self.save()
        return self.data["users"][user_id_str]

    def update_user_data(self, user_id: int, updates: dict) -> None:
        """Update user data and persist."""
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {}
        self.data["users"][user_id_str].update(updates)
        self.save()

    # ---------- feedback API ----------

    def save_feedback(self, feedback_id: str, data: dict) -> None:
        """Persist single feedback record."""
        if "feedbacks" not in self.data:
            self.data["feedbacks"] = {}
        self.data["feedbacks"][feedback_id] = data
        self.save()

    def get_feedback(self, feedback_id: str) -> Optional[dict]:
        """Get feedback record by ID."""
        return self.data.get("feedbacks", {}).get(feedback_id)

    def update_feedback(self, feedback_id: str, updates: dict) -> None:
        """Update existing feedback record."""
        feedbacks = self.data.get("feedbacks", {})
        if feedback_id not in feedbacks:
            logger.warning(
                "Attempted to update non-existing feedback %s",
                feedback_id,
            )
            return
        feedbacks[feedback_id].update(updates)
        self.save()

    def get_feedback_cooldown(
        self,
        user_id: int,
        feedback_type: str,
    ) -> Optional[datetime]:
        """
        Get last feedback datetime for given user & type.
        Returns None if no cooldown exists or if date is invalid.
        """
        cd = self.data.get("feedback_cooldowns", {})
        user_cd = cd.get(str(user_id), {})
        ts_str = user_cd.get(feedback_type)
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str)
        except Exception:
            return None

    def set_feedback_cooldown(
        self,
        user_id: int,
        feedback_type: str,
        when: datetime,
    ) -> None:
        """Persist last feedback time for given user & type."""
        if "feedback_cooldowns" not in self.data:
            self.data["feedback_cooldowns"] = {}
        user_id_str = str(user_id)
        if user_id_str not in self.data["feedback_cooldowns"]:
            self.data["feedback_cooldowns"][user_id_str] = {}
        self.data["feedback_cooldowns"][user_id_str][feedback_type] = when.isoformat()
        self.save()

    # ---------- stats ----------

    def get_stats(self, recent_days: int = 30) -> dict:
        """Get statistics, including recent period and auto-close stats."""
        tickets = self.get_all_tickets()

        # Rating stats
        rated_values = [
            t.rating
            for t in tickets
            if getattr(t, "rated", False) and t.rating is not None
        ]
        rated_tickets = len(rated_values)
        avg_rating = sum(rated_values) / rated_tickets if rated_tickets else None

        # Auto-close candidates: tickets where last move was by support
        # and status is still open (new/working)
        auto_close_waiting = len(
            [
                t
                for t in tickets
                if t.status in ["new", "working"]
                and getattr(t, "last_actor", None) == "support"
            ]
        )

        stats: dict = {
            "total_users": len(self.data["users"]),
            "total_tickets": len(tickets),
            "active_tickets": len(
                [t for t in tickets if t.status in ["new", "working"]]
            ),
            "closed_tickets": len([t for t in tickets if t.status == "done"]),
            "rated_tickets": rated_tickets,
            "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
            "auto_close_waiting": auto_close_waiting,
        }

        # Recent period stats (rolling last N days)
        try:
            now = datetime.now(TIMEZONE)
        except Exception:
            now = datetime.utcnow()
        cutoff = now - timedelta(days=recent_days)

        recent_created = 0
        recent_closed = 0

        for t in tickets:
            # created
            created_at = getattr(t, "created_at", None)
            if isinstance(created_at, datetime):
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=TIMEZONE)
                if created_at >= cutoff:
                    recent_created += 1

            # closed in period
            if t.status == "done":
                last_activity = getattr(t, "last_activity_at", None)
                if isinstance(last_activity, datetime):
                    if last_activity.tzinfo is None:
                        last_activity = last_activity.replace(tzinfo=TIMEZONE)
                    if last_activity >= cutoff:
                        recent_closed += 1

        stats["recent_days"] = recent_days
        stats["recent_created"] = recent_created
        stats["recent_closed"] = recent_closed

        return stats


# Global instance
data_manager = DataManager()
