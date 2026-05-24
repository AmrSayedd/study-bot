import os
import re
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from services.lecture_processor import LectureProcessor
from services.revision_service import RevisionService
from services.doc_reader import extract_urls, fetch_url
from database.db import Database
from ai.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000
MAX_HISTORY = 50
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

    def _get_tz_offset(self, user_id: int) -> int:
        offset_str = self.db.get_preference(user_id, "timezone_offset")
        if offset_str:
            try:
                return int(offset_str)
            except ValueError:
                pass
        return 0

    def _parse_reminder_at(self, raw: str, user_id: int) -> str | None:
        """Parse REMINDER_AT and return absolute UTC timestamp or None.
           Supports: HH:MM (local), +N (relative min), HH:MM+Nd (local+days), plain number (legacy)"""
        if not raw:
            return None
        now = datetime.now(timezone.utc)
        raw = raw.strip()

        # +N relative minutes
        if raw.startswith("+"):
            try:
                minutes = int(raw[1:])
                utc_time = now + timedelta(minutes=minutes)
                if utc_time <= now:
                    utc_time += timedelta(days=1)
                result = utc_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Computed reminder_at: {result} (+{minutes} min)")
                return result
            except (ValueError, TypeError):
                return None

        # HH:MM+Nd (local time + day offset)
        day_match = re.match(r'^(\d{1,2}):(\d{2})\+(\d+)d$', raw)
        if day_match:
            hour, minute, days = int(day_match.group(1)), int(day_match.group(2)), int(day_match.group(3))
            tz = self._get_tz_offset(user_id)
            local_now = now + timedelta(hours=tz)
            target_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days)
            if target_local <= local_now:
                target_local += timedelta(days=1)
            target_utc = target_local - timedelta(hours=tz)
            result = target_utc.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Computed reminder_at: {result} (local {hour:02d}:{minute:02d}+{days}d, UTC{tz:+d})")
            return result

        # HH:MM (local time)
        time_match = re.match(r'^(\d{1,2}):(\d{2})$', raw)
        if time_match:
            hour, minute = int(time_match.group(1)), int(time_match.group(2))
            tz = self._get_tz_offset(user_id)
            local_now = now + timedelta(hours=tz)
            target_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_local <= local_now:
                target_local += timedelta(days=1)
            target_utc = target_local - timedelta(hours=tz)
            result = target_utc.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Computed reminder_at: {result} (local {hour:02d}:{minute:02d}, UTC{tz:+d})")
            return result

        # Legacy: plain number (minutes from now)
        try:
            minutes = int(raw)
            utc_time = now + timedelta(minutes=minutes)
            if utc_time <= now:
                utc_time += timedelta(days=1)
            result = utc_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Computed reminder_at: {result} (+{minutes} min, legacy)")
            return result
        except (ValueError, TypeError):
            return None

    async def _reply(self, update: Update, text: str):
        if not text:
            return
        for chunk in split_message(text):
            if chunk:
                try:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                except BadRequest:
                    try:
                        await update.message.reply_text(chunk)
                    except Exception as e:
                        logger.error(f"Failed to send reply: {e}")

    async def _deliver_overdue_reminders(self, update: Update, reminders: list[dict]):
        if not reminders:
            return
        claimed = [r for r in reminders if self.db.try_claim_reminder(r["id"])]
        if not claimed:
            return
        lines = ["\U0001F4CC *Your pending reminders:*"]
        for r in claimed:
            tag = ""
            if r["course"]:
                tag = f" [{r['course']}"
                if r["lecture"]:
                    tag += f" \u2192 {r['lecture']}"
                tag += "]"
            lines.append(f"\u2022 {r['content']}{tag}")
        msg = "\n".join(lines)
        for chunk in split_message(msg):
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except BadRequest:
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.error(f"Failed to deliver reminder: {e}")
        for r in claimed:
            self.db.update_reminder_schedule(r["id"], True)

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

        await self._deliver_overdue_reminders(update, ctx["reminders"])

        # Handle time questions server-side (AI fabricates times from training data)
        time_lower = text.lower()
        if any(phrase in time_lower for phrase in ["what time", "current time", "what's the time", "what is the time"]):
            # Also check if user provided their offset in the same message
            tz_match = re.search(r'UTC([+-]\d+)', text)
            if tz_match:
                offset = tz_match.group(1)
                self.db.set_preference(user_id, "timezone_offset", offset)
                now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                reply = f"The current server time is {now_utc} (your saved offset: UTC{offset})."
                await self._reply(update, reply)
                return
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            tz = ctx.get("timezone_offset", "")
            if tz:
                reply = f"The current server time is {now_utc} (your offset: UTC{tz})."
            else:
                reply = (
                    f"The current server time is {now_utc}.\n"
                    "To convert to your local time, tell me your UTC offset "
                    "(e.g., `I am UTC+2`) and I will save it."
                )
            await self._reply(update, reply)
            return

        response_data = self.ai.chat(text, ctx)
        reply = response_data["text"]
        updates = response_data["state_updates"]

        if not reply:
            await update.message.reply_text("Sorry, I couldn't process that.")
            return

        updates["course_title"] = ctx["course"]
        updates["lecture_title"] = ctx["lecture"]

        if "reminder_at" in updates:
            parsed = self._parse_reminder_at(updates["reminder_at"], user_id)
            if parsed:
                updates["reminder_at"] = parsed
            else:
                logger.warning(f"Invalid REMINDER_AT value: {updates.get('reminder_at')}, falling back to default")
                del updates["reminder_at"]

        self.db.save_chat_interaction(user_id, text, reply, updates)

        await self._reply(update, reply)

    async def _handle_image(self, update: Update, file_path: str, caption: str):
        user_id = update.effective_user.id
        ctx = self.db.get_chat_context(user_id)

        await self._deliver_overdue_reminders(update, ctx["reminders"])

        response_data = self.ai.chat_with_image(file_path, caption or "", ctx)
        reply = response_data["text"]
        updates = response_data["state_updates"]

        user_text = caption or "[Sent an image]"
        updates["course_title"] = ctx["course"]
        updates["lecture_title"] = ctx["lecture"]

        if "reminder_at" in updates:
            parsed = self._parse_reminder_at(updates["reminder_at"], user_id)
            if parsed:
                updates["reminder_at"] = parsed
            else:
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

        ctx = self.db.get_chat_context(user_id)
        await self._deliver_overdue_reminders(update, ctx["reminders"])

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
