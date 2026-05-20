import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.lecture_processor import LectureProcessor
from services.reminder_service import ReminderService
from services.revision_service import RevisionService
from database.db import Database
from ai.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(self, db: Database, ai: GeminiClient):
        self.db = db
        self.ai = ai
        self.processor = LectureProcessor()
        self.reminder_service = ReminderService(db)
        self.revision_service = RevisionService(db, ai)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()

        if not text:
            return

        session = self.db.get_or_create_session(user_id)

        due_reminders = self.reminder_service.get_due_reminders(user_id)
        reminder_msg = ""
        if due_reminders:
            reminder_msg = self.reminder_service.format_reminder_message(due_reminders)
            for r in due_reminders:
                self.db.update_reminder_schedule(r["id"], True)

        weak = self.db.get_weak_topics(user_id)
        course = ""
        lecture = ""
        if session.get("current_course_id"):
            c = self.db.get_course(session["current_course_id"])
            if c:
                course = c["title"]
        if session.get("current_lecture_id"):
            l = self.db.get_lecture(session["current_lecture_id"])
            if l:
                lecture = l["title"]

        history = __import__("json").loads(session.get("history", "[]"))

        response_data = self.ai.chat(text, {
            "course": course,
            "lecture": lecture,
            "mode": session.get("revision_mode", "daily"),
            "weak_topics": [w["topic"] for w in weak],
            "history": history,
        })

        reply = response_data["text"]
        updates = response_data["state_updates"]

        if reminder_msg:
            reply = f"{reminder_msg}\n\n{reply}"

        if "course" in updates:
            new_course = self.db.find_or_create_course(updates["course"], user_id)
            self.db.update_session(user_id, current_course_id=new_course["id"])
            course = new_course["title"]
        if "lecture" in updates:
            cid = session.get("current_course_id")
            if not cid and course:
                c = self.db.find_or_create_course(course, user_id)
                cid = c["id"]
            if cid:
                new_lecture = self.db.find_or_create_lecture(cid, updates["lecture"])
                self.db.update_session(user_id, current_lecture_id=new_lecture["id"])
                lecture = new_lecture["title"]
        if "mode" in updates:
            self.db.update_session(user_id, revision_mode=updates["mode"])
        if "reminder" in updates:
            self.reminder_service.create_reminder(
                user_id, updates["reminder"], course or None, lecture or None
            )

        self.db.add_to_history(user_id, "user", text)
        self.db.add_to_history(user_id, "assistant", reply)

        await update.message.reply_text(reply)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        doc = update.message.document

        if not doc.file_name:
            await update.message.reply_text("Please send a file with a name.")
            return

        ext = os.path.splitext(doc.file_name)[1].lower()
        if ext not in (".pdf", ".txt", ".md"):
            await update.message.reply_text(
                "I can only process PDF, TXT, and Markdown files."
            )
            return

        await update.message.reply_text("Downloading your file...")

        try:
            file = await doc.get_file()
            file_bytes = await file.download_as_bytearray()
            file_path = self.processor.save_file(doc.file_name, bytes(file_bytes))
            extracted = self.processor.extract_text(file_path)

            if not extracted.strip():
                await update.message.reply_text(
                    "I couldn't extract any text from that file. "
                    "Please make sure it's a text-based file."
                )
                return

            await update.message.reply_text(
                f"Extracted {len(extracted)} characters. Processing..."
            )

            result = self.revision_service.process_upload(
                user_id, file_path, doc.file_name, extracted
            )

            reply = (
                f"✅ Processed! Added to course *{result['course']}* → "
                f"lecture *{result['lecture']}*.\n\n"
                f"{result['summary']}\n\n"
                f"Generated {result['question_count']} revision questions. "
                f"Ready to revise whenever you like!"
            )

            self.db.add_to_history(user_id, "user", f"[Uploaded file: {doc.file_name}]")
            self.db.add_to_history(user_id, "assistant", reply)

            await update.message.reply_text(reply, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"File processing error: {e}")
            await update.message.reply_text(
                "Sorry, I ran into an error processing that file. "
                "Please try again or use a different file."
            )
