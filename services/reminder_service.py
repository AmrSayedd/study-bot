import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ReminderService:
    def __init__(self, db):
        self.db = db

    def create_reminder(self, user_id: int, content: str,
                        course: str = None, lecture: str = None) -> dict:
        reminder = self.db.create_reminder(user_id, content, course, lecture)
        logger.info(f"Created reminder {reminder['id']} for user {user_id}: {content[:50]}")
        return reminder

    def get_due_reminders(self, user_id: int) -> list[dict]:
        return self.db.get_due_reminders(user_id)

    def format_reminder_message(self, reminders: list[dict]) -> str:
        if not reminders:
            return ""
        lines = ["📌 *Here are your pending reminders:*"]
        for r in reminders:
            context = ""
            if r["course"]:
                context += f" [{r['course']}"
                if r["lecture"]:
                    context += f" → {r['lecture']}"
                context += "]"
            lines.append(f"• {r['content']}{context}")
        return "\n".join(lines)
