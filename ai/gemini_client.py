from datetime import datetime, timezone
from google import genai
from google.genai import types
import json
import re
import logging
import io
import PIL.Image
from . import prompts
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def _generate(self, prompt: str, system_instruction: str = None) -> str:
        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(system_instruction=system_instruction)
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ""

    def _generate_with_history(self, history: list, prompt: str, system_instruction: str = None) -> str:
        try:
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part(text=msg["text"])]
                ))
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=prompt)]
            ))

            config = None
            if system_instruction:
                config = types.GenerateContentConfig(system_instruction=system_instruction)

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            return ""

    def chat_with_image(self, image_path: str, caption: str, context: dict) -> dict:
        course = context.get("course", "")
        lecture = context.get("lecture", "")
        mode = context.get("mode", "daily")
        weak_topics = ", ".join(context.get("weak_topics", [])) or "none"
        preferences = context.get("preferences", "")
        history = context.get("history", [])
        current_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        tz_offset = context.get("timezone_offset", "")

        system = prompts.SYSTEM_PROMPT.format(
            course=course or "not set",
            lecture=lecture or "not set",
            mode=mode,
            weak_topics=weak_topics,
            preferences=preferences or "none",
            current_time=current_utc,
            timezone_offset=tz_offset or "unknown",
            vocabulary=context.get("vocabulary", "") or "none",
            all_courses=context.get("all_courses", "") or "none",
            all_notes=context.get("all_notes", "") or "none",
        )

        try:
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part(text=msg["text"])]
                ))

            img = PIL.Image.open(image_path)
            buffer = io.BytesIO()
            img.save(buffer, format=img.format or "PNG")
            img_bytes = buffer.getvalue()
            mime = f"image/{img.format.lower()}" if img.format else "image/png"

            user_parts = [types.Part(inline_data=types.Blob(mime_type=mime, data=img_bytes))]
            if caption and caption.strip():
                user_parts.append(types.Part(text=caption.strip()))
            contents.append(types.Content(role="user", parts=user_parts))

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system),
            )
            raw = response.text
        except Exception as e:
            logger.error(f"Gemini image chat error: {e}")
            return {"text": "Sorry, I couldn't process that image.", "state_updates": {}}

        text, state_updates = self._parse_response(raw)
        text = self._strip_time_references(text)
        return {"text": text, "state_updates": state_updates}

    def chat(self, user_text: str, context: dict) -> dict:
        course = context.get("course", "")
        lecture = context.get("lecture", "")
        mode = context.get("mode", "daily")
        weak_topics = ", ".join(context.get("weak_topics", [])) or "none"
        preferences = context.get("preferences", "")
        history = context.get("history", [])
        current_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        tz_offset = context.get("timezone_offset", "")

        system = prompts.SYSTEM_PROMPT.format(
            course=course or "not set",
            lecture=lecture or "not set",
            mode=mode,
            weak_topics=weak_topics,
            preferences=preferences or "none",
            current_time=current_utc,
            timezone_offset=tz_offset or "unknown",
            vocabulary=context.get("vocabulary", "") or "none",
            all_courses=context.get("all_courses", "") or "none",
            all_notes=context.get("all_notes", "") or "none",
        )

        raw = self._generate_with_history(history, user_text, system)

        text, state_updates = self._parse_response(raw)
        text = self._strip_time_references(text)
        return {
            "text": text,
            "state_updates": state_updates,
        }

    def _strip_time_references(self, text: str) -> str:
        """Remove sentences that mention current time (AI fabricates these)."""
        lines = text.split("\n")
        clean = []
        for line in lines:
            lower = line.strip().lower()
            if re.search(r'\b\d{1,2}:\d{2}\s*(am|pm)\s*utc\b', lower):
                continue
            if re.search(r'^(given )?the current (utc )?time is', lower):
                continue
            if re.search(r'\d+\s*minutes? (from now|away)', lower):
                continue
            clean.append(line)
        return "\n".join(clean).strip()

    def _parse_response(self, raw: str) -> tuple:
        text = raw
        state_updates = {}

        lines = raw.split("\n")
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("COURSE:"):
                val = stripped[len("COURSE:"):].strip()
                if val:
                    state_updates["course"] = val
            elif stripped.startswith("LECTURE:"):
                val = stripped[len("LECTURE:"):].strip()
                if val:
                    state_updates["lecture"] = val
            elif stripped.startswith("MODE:"):
                val = stripped[len("MODE:"):].strip().lower()
                if val in ("daily", "deep", "teaching", "oral_exam"):
                    state_updates["mode"] = val
            elif stripped.startswith("REMINDER_AT:"):
                val = stripped[len("REMINDER_AT:"):].strip()
                if val:
                    state_updates["reminder_at"] = val
                    logger.info(f"REMINDER_AT extracted (raw): {val}")
            elif stripped.startswith("REMINDER:"):
                val = stripped[len("REMINDER:"):].strip()
                if val:
                    state_updates["reminder"] = val
                    logger.info(f"REMINDER extracted: {val}")
            elif stripped.startswith("WEAK_TOPIC:"):
                val = stripped[len("WEAK_TOPIC:"):].strip()
                if val:
                    state_updates.setdefault("weak_topics", []).append(val)
            elif stripped.startswith("NOTE:"):
                val = stripped[len("NOTE:"):].strip()
                if val:
                    parts = [p.strip() for p in val.split("|")]
                    entry = {"topic": parts[0]}
                    if len(parts) > 1:
                        entry["content"] = parts[1]
                    state_updates.setdefault("notes", []).append(entry)
                    logger.info(f"NOTE extracted: {entry}")
            elif stripped.startswith("WORD:"):
                val = stripped[len("WORD:"):].strip()
                if val:
                    parts = [p.strip() for p in val.split("|")]
                    entry = {"word": parts[0]}
                    if len(parts) > 1:
                        entry["meaning"] = parts[1]
                    if len(parts) > 2:
                        entry["example"] = parts[2]
                    state_updates.setdefault("words", []).append(entry)
                    logger.info(f"WORD extracted: {entry}")
            elif stripped.startswith("PREFERENCE:"):
                val = stripped[len("PREFERENCE:"):].strip()
                if val and "=" in val:
                    key, _, value = val.partition("=")
                    state_updates.setdefault("preferences", []).append((key.strip(), value.strip()))
                elif val and ":" in val:
                    key, _, value = val.partition(":")
                    state_updates.setdefault("preferences", []).append((key.strip(), value.strip()))
            else:
                clean_lines.append(line)

        text = "\n".join(clean_lines).strip()
        return text, state_updates

    def generate_lecture_content(self, title: str, course: str, text: str) -> dict:
        prompt = prompts.GENERATE_LECTURE_CONTENT.format(
            title=title,
            course=course,
            text=text
        )
        raw = self._generate(prompt)
        return self._safe_parse_json(raw, {
            "summary": "",
            "key_concepts": [],
            "important_equations": [],
            "common_misconceptions": [],
            "questions": [],
        })

    def parse_upload_intent(self, text_excerpt: str, current_course: str = "",
                            current_lecture: str = "") -> dict:
        prompt = prompts.PARSE_UPLOAD_INTENT.format(
            current_course=current_course or "none",
            current_lecture=current_lecture or "none",
            text_excerpt=text_excerpt[:2000],
        )
        raw = self._generate(prompt)
        return self._safe_parse_json(raw, {
            "course": None,
            "lecture": None,
            "suggested_course": None,
            "suggested_lecture": None,
        })

    def generate_follow_up(self, topic: str, answer: str) -> str:
        prompt = prompts.GENERATE_FOLLOW_UP.format(topic=topic, answer=answer)
        return self._generate(prompt)

    def _safe_parse_json(self, raw: str, default: dict) -> dict:
        if not raw:
            return default
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from Gemini: {raw[:200]}")
            return default
