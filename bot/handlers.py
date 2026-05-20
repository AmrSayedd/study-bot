import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.lecture_processor import LectureProcessor
from services.revision_service import RevisionService
from database.db import Database
from ai.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000


def split_message(text: str) -> list[str]:
    if len(text) <= MAX_MSG_LEN:
        return [text]
    chunks = []
    while len(text) > MAX_MSG_LEN:
        cut = text.rfind("\n\n", 0, MAX_MSG_LEN)
        if cut == -1:
            cut = text.rfind(". ", 0, MAX_MSG_LEN)
            if cut != -1:
                cut += 1
        if cut == -1:
            cut = text.rfind(" ", 0, MAX_MSG_LEN)
        if cut == -1:
            cut = MAX_MSG_LEN
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks


class BotHandlers:
    def __init__(self, db: Database, ai: GeminiClient):
        self.db = db
        self.ai = ai
        self.processor = LectureProcessor()
        self.revision_service = RevisionService(db, ai)

    async def _reply(self, update: Update, text: str):
        for chunk in split_message(text):
            await update.message.reply_text(chunk)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        if not text:
            return

        ctx = self.db.get_chat_context(user_id)

        reminder_msg = ""
        if ctx["reminders"]:
            lines = ["\U0001F4CC *Here are your pending reminders:*"]
            for r in ctx["reminders"]:
                tag = f" [{r['course']}" + (f" \u2192 {r['lecture']}]" if r["lecture"] else "]") if r["course"] else ""
                lines.append(f"\u2022 {r['content']}{tag}")
            reminder_msg = "\n".join(lines)
            for r in ctx["reminders"]:
                self.db.update_reminder_schedule(r["id"], True)

        response_data = self.ai.chat(text, ctx)
        reply = response_data["text"]
        updates = response_data["state_updates"]

        if reminder_msg:
            reply = f"{reminder_msg}\n\n{reply}"

        updates["course_title"] = ctx["course"]
        updates["lecture_title"] = ctx["lecture"]

        self.db.save_chat_interaction(user_id, text, reply, updates)

        await self._reply(update, reply)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        doc = update.message.document

        if not doc.file_name:
            await update.message.reply_text("Please send a file with a name.")
            return

        ext = os.path.splitext(doc.file_name)[1].lower()
        if ext not in (".pdf", ".txt", ".md"):
            await update.message.reply_text("I can only process PDF, TXT, and Markdown files.")
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
                f"\u2705 Processed! Added to course *{result['course']}* \u2192 "
                f"lecture *{result['lecture']}*.\n\n"
                f"{result['summary']}\n\n"
                f"Generated {result['question_count']} revision questions. "
                f"Ready to revise whenever you like!"
            )

            self.db.add_to_history(user_id, "user", f"[Uploaded file: {doc.file_name}]")
            self.db.add_to_history(user_id, "assistant", reply)

            for chunk in split_message(reply):
                await update.message.reply_text(chunk, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"File processing error: {e}")
            await update.message.reply_text(
                "Sorry, I ran into an error processing that file. "
                "Please try again or use a different file."
            )
