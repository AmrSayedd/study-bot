import os
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from services.lecture_processor import LectureProcessor
from services.revision_service import RevisionService
from services.doc_reader import extract_urls, fetch_url
from database.db import Database
from ai.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


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
        if not text:
            return
        for chunk in split_message(text):
            if chunk:
                await update.message.reply_text(chunk, parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        if not text:
            return

        ctx = self.db.get_chat_context(user_id)

        urls = extract_urls(text)
        doc_text = ""
        for url in urls[:3]:
            fetched = fetch_url(url)
            if fetched:
                doc_text += f"\n--- Content from {url} ---\n{fetched}\n"

        if doc_text:
            text = f"{text}\n\n[The user shared the following documentation from a URL. Read and understand it to answer their question.]\n{doc_text}"

        if ctx["reminders"]:
            for r in ctx["reminders"]:
                self.db.update_reminder_schedule(r["id"], True)

        response_data = self.ai.chat(text, ctx)
        reply = response_data["text"]
        updates = response_data["state_updates"]

        if not reply:
            await update.message.reply_text("Sorry, I couldn't process that.")
            return

        updates["course_title"] = ctx["course"]
        updates["lecture_title"] = ctx["lecture"]

        if "reminder_at" in updates:
            try:
                minutes = int(updates["reminder_at"])
                now = datetime.now(timezone.utc)
                utc_time = now + timedelta(minutes=minutes)
                if utc_time <= now:
                    utc_time = now + timedelta(days=1)
                updates["reminder_at"] = utc_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Computed reminder_at: {updates['reminder_at']} (+{minutes} min from now)")
            except (ValueError, TypeError):
                logger.warning(f"Invalid REMINDER_AT value: {updates.get('reminder_at')}, falling back to default")
                del updates["reminder_at"]

        self.db.save_chat_interaction(user_id, text, reply, updates)

        await self._reply(update, reply)

    async def _handle_image(self, update: Update, file_path: str, caption: str):
        user_id = update.effective_user.id
        ctx = self.db.get_chat_context(user_id)

        if ctx["reminders"]:
            for r in ctx["reminders"]:
                self.db.update_reminder_schedule(r["id"], True)

        response_data = self.ai.chat_with_image(file_path, caption or "", ctx)
        reply = response_data["text"]
        updates = response_data["state_updates"]

        user_text = caption or "[Sent an image]"
        updates["course_title"] = ctx["course"]
        updates["lecture_title"] = ctx["lecture"]

        if "reminder_at" in updates:
            try:
                minutes = int(updates["reminder_at"])
                now = datetime.now(timezone.utc)
                utc_time = now + timedelta(minutes=minutes)
                if utc_time <= now:
                    utc_time = now + timedelta(days=1)
                updates["reminder_at"] = utc_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Computed reminder_at: {updates['reminder_at']} (+{minutes} min from now)")
            except (ValueError, TypeError):
                logger.warning(f"Invalid REMINDER_AT value: {updates.get('reminder_at')}, falling back to default")
                del updates["reminder_at"]

        self.db.save_chat_interaction(user_id, user_text, reply, updates)

        await self._reply(update, reply)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo = update.message.photo[-1]
        caption = update.message.caption or ""
        try:
            file = await photo.get_file()
            file_bytes = await file.download_as_bytearray()
            ext = ".jpg"
            file_name = f"photo_{update.message.message_id}{ext}"
            file_path = self.processor.save_file(file_name, bytes(file_bytes))
            await self._handle_image(update, file_path, caption)
        except Exception as e:
            logger.error(f"Photo error: {e}")
            await update.message.reply_text("Sorry, I couldn't process that image.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        doc = update.message.document

        if not doc.file_name:
            await update.message.reply_text("Please send a file with a name.")
            return

        ext = os.path.splitext(doc.file_name)[1].lower()

        if ext in IMAGE_EXTS:
            try:
                file = await doc.get_file()
                file_bytes = await file.download_as_bytearray()
                file_path = self.processor.save_file(doc.file_name, bytes(file_bytes))
                await self._handle_image(update, file_path, update.message.caption or "")
            except Exception as e:
                logger.error(f"Image document error: {e}")
                await update.message.reply_text("Sorry, I couldn't process that image.")
            return

        if ext not in (".pdf", ".txt", ".md"):
            await update.message.reply_text("I can only process PDF, TXT, Markdown, and image files.")
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
