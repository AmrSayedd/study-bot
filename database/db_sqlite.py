import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from .models import ALL_TABLES
from config import DATABASE_PATH


logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        import os
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        for stmt in ALL_TABLES:
            cur.execute(stmt)
        self.conn.commit()

    def _row_to_dict(self, row):
        return dict(row) if row else None

    # -- Courses --
    def create_course(self, title: str, user_id: int) -> dict:
        cur = self.conn.execute(
            "INSERT INTO courses (title, user_id) VALUES (?, ?)",
            (title, user_id)
        )
        self.conn.commit()
        return self.get_course(cur.lastrowid)

    def get_courses(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM courses WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_course(self, course_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def find_course_by_title(self, title: str, user_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM courses WHERE LOWER(title) = LOWER(?) AND user_id = ?",
            (title, user_id)
        ).fetchone()
        return self._row_to_dict(row)

    def find_or_create_course(self, title: str, user_id: int) -> dict:
        course = self.find_course_by_title(title, user_id)
        if course:
            return course
        return self.create_course(title, user_id)

    # -- Lectures --
    def create_lecture(self, course_id: int, title: str, summary: str = None,
                       key_concepts: str = None, important_equations: str = None,
                       common_misconceptions: str = None,
                       compressed_knowledge: str = None) -> dict:
        cur = self.conn.execute(
            """INSERT INTO lectures
               (course_id, title, summary, key_concepts, important_equations,
                common_misconceptions, compressed_knowledge)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (course_id, title, summary, key_concepts, important_equations,
             common_misconceptions, compressed_knowledge)
        )
        self.conn.commit()
        return self.get_lecture(cur.lastrowid)

    def get_lectures(self, course_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM lectures WHERE course_id = ? ORDER BY created_at DESC",
            (course_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_lecture(self, lecture_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM lectures WHERE id = ?", (lecture_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def find_lecture_by_title(self, course_id: int, title: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM lectures WHERE course_id = ? AND LOWER(title) = LOWER(?)",
            (course_id, title)
        ).fetchone()
        return self._row_to_dict(row)

    def find_or_create_lecture(self, course_id: int, title: str) -> dict:
        lecture = self.find_lecture_by_title(course_id, title)
        if lecture:
            return lecture
        return self.create_lecture(course_id, title)

    def get_recent_lectures(self, user_id: int, limit: int = 5) -> list[dict]:
        rows = self.conn.execute(
            """SELECT l.*, c.title as course_title
               FROM lectures l
               JOIN courses c ON c.id = l.course_id
               WHERE c.user_id = ?
               ORDER BY l.created_at DESC LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Lecture Sources --
    def add_lecture_source(self, lecture_id: int, filename: str,
                           original_text: str, file_type: str) -> dict:
        cur = self.conn.execute(
            "INSERT INTO lecture_sources (lecture_id, filename, original_text, file_type) VALUES (?, ?, ?, ?)",
            (lecture_id, filename, original_text, file_type)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM lecture_sources WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def get_lecture_sources(self, lecture_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM lecture_sources WHERE lecture_id = ?",
            (lecture_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Questions --
    def create_question(self, lecture_id: int, question_type: str,
                        question_text: str, answer_text: str = None,
                        difficulty: int = 1) -> dict:
        cur = self.conn.execute(
            """INSERT INTO questions
               (lecture_id, question_type, question_text, answer_text, difficulty)
               VALUES (?, ?, ?, ?, ?)""",
            (lecture_id, question_type, question_text, answer_text, difficulty)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM questions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def get_questions_by_lecture(self, lecture_id: int, qtype: str = None) -> list[dict]:
        if qtype:
            rows = self.conn.execute(
                "SELECT * FROM questions WHERE lecture_id = ? AND question_type = ?",
                (lecture_id, qtype)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM questions WHERE lecture_id = ?", (lecture_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_question(self, question_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        return self._row_to_dict(row)

    # -- Reminders --
    def create_reminder(self, user_id: int, content: str,
                        course: str = None, lecture: str = None,
                        reminder_at: str = None) -> dict:
        existing = self.conn.execute(
            """SELECT * FROM reminders
               WHERE user_id = ? AND LOWER(content) = LOWER(?)
               AND COALESCE(course,'') = COALESCE(?,'')
               AND COALESCE(lecture,'') = COALESCE(?,'')
               AND next_review_at > datetime('now')
               ORDER BY next_review_at DESC LIMIT 1""",
            (user_id, content, course or '', lecture or '')
        ).fetchone()
        if existing:
            eid = existing["id"]
            if reminder_at:
                self.conn.execute(
                    "UPDATE reminders SET next_review_at = ? WHERE id = ?",
                    (reminder_at, eid)
                )
            else:
                self.conn.execute(
                    "UPDATE reminders SET next_review_at = datetime('now', '+1 day') WHERE id = ?",
                    (eid,)
                )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (eid,)
            ).fetchone()
            result = dict(row)
            logger.info(f"Reminder updated (existing): id={result['id']}, next_review_at={result['next_review_at']}")
            return result
        self.dedup_reminders(user_id)
        if reminder_at:
            logger.info(f"Creating reminder for user {user_id} with reminder_at={reminder_at}")
            cur = self.conn.execute(
                """INSERT INTO reminders (user_id, content, course, lecture, next_review_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, content, course, lecture, reminder_at)
            )
        else:
            logger.info(f"Creating reminder for user {user_id} with +1 day default")
            cur = self.conn.execute(
                """INSERT INTO reminders (user_id, content, course, lecture, next_review_at)
                   VALUES (?, ?, ?, ?, datetime('now', '+1 day'))""",
                (user_id, content, course, lecture)
            )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        result = dict(row)
        logger.info(f"Reminder stored: id={result['id']}, next_review_at={result['next_review_at']}")
        return result

    def dedup_reminders(self, user_id: int):
        """Remove duplicate reminders keeping only the newest per (content, course, lecture)."""
        self.conn.execute(
            """DELETE FROM reminders WHERE id NOT IN (
                SELECT MAX(id) FROM reminders
                WHERE user_id = ?
                GROUP BY LOWER(content), COALESCE(course,''), COALESCE(lecture,'')
            ) AND user_id = ?""",
            (user_id, user_id)
        )
        self.conn.commit()

    def get_due_reminders(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM reminders WHERE user_id = ? AND next_review_at <= datetime('now') ORDER BY next_review_at",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_users_with_due_reminders(self) -> list[int]:
        rows = self.conn.execute(
            "SELECT DISTINCT user_id FROM reminders WHERE next_review_at <= datetime('now')"
        ).fetchall()
        return [r["user_id"] for r in rows]

    def try_claim_reminder(self, reminder_id: int) -> bool:
        """Atomically claim a reminder. Returns True if we own it, False if already claimed."""
        cur = self.conn.execute(
            """UPDATE reminders SET next_review_at = datetime('now', '+1 second')
               WHERE id = ? AND next_review_at <= datetime('now')""",
            (reminder_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def update_reminder_schedule(self, reminder_id: int, correct: bool):
        reminder = self.conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        ).fetchone()
        if not reminder:
            return
        r = dict(reminder)
        if correct:
            new_interval = r["interval_days"] * 2.0
            new_reps = r["repetitions"] + 1
        else:
            new_interval = 1.0
            new_reps = 0
        self.conn.execute(
            "UPDATE reminders SET interval_days = ?, repetitions = ?, next_review_at = datetime('now', ? || ' days') WHERE id = ?",
            (new_interval, new_reps, str(new_interval), reminder_id)
        )
        self.conn.commit()

    # -- Performance Tracking --
    def record_answer(self, user_id: int, question_id: int = None,
                      lecture_id: int = None, course_id: int = None,
                      topic: str = None, correct: bool = None,
                      confidence: int = None):
        self.conn.execute(
            """INSERT INTO performance_tracking
               (user_id, question_id, lecture_id, course_id, topic, correct, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, question_id, lecture_id, course_id, topic, correct, confidence)
        )
        self.conn.commit()

    def get_weak_topics(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT topic, COUNT(*) as attempts,
                      SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END) as mistakes,
                      ROUND(AVG(confidence), 1) as avg_confidence
               FROM performance_tracking
               WHERE user_id = ? AND topic IS NOT NULL
               GROUP BY topic
               HAVING mistakes > 0 OR avg_confidence < 3
               ORDER BY mistakes DESC, avg_confidence ASC
               LIMIT 10""",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_performance_summary(self, user_id: int) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) as c FROM performance_tracking WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        correct = self.conn.execute(
            "SELECT COUNT(*) as c FROM performance_tracking WHERE user_id = ? AND correct = 1",
            (user_id,)
        ).fetchone()
        weak = self.get_weak_topics(user_id)
        return {
            "total_attempts": total["c"] if total else 0,
            "correct": correct["c"] if correct else 0,
            "weak_topics": [w["topic"] for w in weak],
        }

    # -- User Preferences --
    def set_preference(self, user_id: int, key: str, value: str):
        self.conn.execute(
            """INSERT INTO user_preferences (user_id, pref_key, pref_value)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, pref_key) DO UPDATE SET pref_value = ?, updated_at = CURRENT_TIMESTAMP""",
            (user_id, key, value, value)
        )
        self.conn.commit()

    def get_preferences(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT pref_key, pref_value FROM user_preferences WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_preferences_as_text(self, user_id: int) -> str:
        prefs = self.get_preferences(user_id)
        if not prefs:
            return "none"
        return "; ".join(f"{p['pref_key']}: {p['pref_value']}" for p in prefs)

    def get_preference(self, user_id: int, key: str) -> str:
        row = self.conn.execute(
            "SELECT pref_value FROM user_preferences WHERE user_id = ? AND pref_key = ?",
            (user_id, key)
        ).fetchone()
        return row["pref_value"] if row else ""

    # -- Conversation Sessions --
    def get_active_session(self, user_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM conversation_sessions WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_or_create_session(self, user_id: int) -> dict:
        session = self.get_active_session(user_id)
        if session:
            return session
        self.conn.execute(
            "INSERT INTO conversation_sessions (user_id) VALUES (?)",
            (user_id,)
        )
        self.conn.commit()
        return self.get_active_session(user_id)

    def get_all_courses(self, user_id: int) -> list[dict]:
        return self.get_courses(user_id)

    def get_course_titles(self, user_id: int) -> str:
        courses = self.get_all_courses(user_id)
        return ", ".join(c["title"] for c in courses) if courses else "none"

    # -- Course Notes --
    def add_note(self, user_id: int, topic: str, content: str,
                  course_id: int = None) -> dict:
        cur = self.conn.execute(
            """INSERT INTO course_notes (user_id, topic, content, course_id)
               VALUES (?, ?, ?, ?)""",
            (user_id, topic, content, course_id)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM course_notes WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def get_notes_grouped(self, user_id: int) -> str:
        rows = self.conn.execute(
            """SELECT n.*, c.title as course_title
               FROM course_notes n
               LEFT JOIN courses c ON c.id = n.course_id
               WHERE n.user_id = ?
               ORDER BY n.course_id NULLS LAST, n.created_at""",
            (user_id,)
        ).fetchall()
        if not rows:
            return ""
        groups = {}
        for r in rows:
            d = dict(r)
            ct = d.get("course_title") or "General"
            groups.setdefault(ct, [])
            groups[ct].append(f"- {d['topic']}: {d['content']}")
        parts = []
        for ct in groups:
            parts.append(f"{ct}:\n" + "\n".join(groups[ct]))
        return "\n\n".join(parts)

    def update_session(self, user_id: int, **kwargs):
        fields = []
        values = []
        for key, val in kwargs.items():
            if key in ("current_course_id", "current_lecture_id", "revision_mode", "history", "active"):
                fields.append(f"{key} = ?")
                if isinstance(val, (list, dict)):
                    values.append(json.dumps(val))
                else:
                    values.append(val)
        if fields:
            values.append(user_id)
            self.conn.execute(
                f"UPDATE conversation_sessions SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                values
            )
            self.conn.commit()

    def add_to_history(self, user_id: int, role: str, text: str, max_history: int = 20):
        session = self.get_or_create_session(user_id)
        history = json.loads(session.get("history", "[]"))
        history.append({"role": role, "text": text})
        if len(history) > max_history:
            history = history[-max_history:]
        self.update_session(user_id, history=json.dumps(history))

    def end_session(self, user_id: int):
        self.conn.execute(
            "DELETE FROM conversation_sessions WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()

    # -- Vocabulary --
    def add_word(self, user_id: int, word: str, meaning: str = "",
                  example: str = "", course_id: int = None,
                  lecture_id: int = None) -> dict:
        cur = self.conn.execute(
            """INSERT INTO vocabulary (user_id, word, meaning, example, course_id, lecture_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, word, meaning, example, course_id, lecture_id)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM vocabulary WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def get_vocabulary(self, user_id: int, course_id: int = None,
                        lecture_id: int = None) -> list[dict]:
        if lecture_id:
            rows = self.conn.execute(
                "SELECT * FROM vocabulary WHERE user_id = ? AND lecture_id = ? ORDER BY created_at",
                (user_id, lecture_id)
            ).fetchall()
        elif course_id:
            rows = self.conn.execute(
                "SELECT * FROM vocabulary WHERE user_id = ? AND course_id = ? ORDER BY created_at",
                (user_id, course_id)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM vocabulary WHERE user_id = ? ORDER BY created_at",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_vocabulary_as_text(self, user_id: int, course_id: int = None,
                                lecture_id: int = None) -> str:
        words = self.get_vocabulary(user_id, course_id, lecture_id)
        if not words:
            return ""
        return "\n".join(
            f"- {w['word']}" + (f": {w['meaning']}" if w['meaning'] else "")
            for w in words
        )

    # -- Consolidated chat context --
    def get_chat_context(self, user_id: int) -> dict:
        session = self.get_or_create_session(user_id)
        course = ""
        lecture = ""
        cid = session.get("current_course_id")
        lid = session.get("current_lecture_id")
        if cid:
            c = self.get_course(cid)
            if c:
                course = c["title"]
        if lid:
            l = self.get_lecture(lid)
            if l:
                lecture = l["title"]
        weak = self.get_weak_topics(user_id)
        prefs = self.get_preferences_as_text(user_id)
        tz_offset = self.get_preference(user_id, "timezone_offset")
        reminders = self.get_due_reminders(user_id)
        vocab = self.get_vocabulary_as_text(user_id, cid, lid)
        all_courses = self.get_course_titles(user_id)
        all_notes = self.get_notes_grouped(user_id)
        return {
            "session": session,
            "course": course,
            "lecture": lecture,
            "mode": session.get("revision_mode", "daily"),
            "weak_topics": [w["topic"] for w in weak],
            "preferences": prefs,
            "timezone_offset": tz_offset,
            "reminders": reminders,
            "vocabulary": vocab,
            "all_courses": all_courses,
            "all_notes": all_notes,
            "history": json.loads(session.get("history", "[]")),
        }

    def save_chat_interaction(self, user_id: int, user_text: str,
                               reply: str, updates: dict):
        session = self.get_or_create_session(user_id)
        history = json.loads(session.get("history", "[]"))
        cid = session.get("current_course_id")
        lid = session.get("current_lecture_id")

        new_cid = cid
        new_lid = lid
        if "course" in updates:
            c = self.find_or_create_course(updates["course"], user_id)
            new_cid = c["id"]
        if "lecture" in updates:
            cc = new_cid or cid
            if cc:
                l = self.find_or_create_lecture(cc, updates["lecture"])
                new_lid = l["id"]

        history.append({"role": "user", "text": user_text})
        history.append({"role": "assistant", "text": reply})
        if len(history) > 20:
            history = history[-20:]

        set_clauses = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if new_cid != cid:
            set_clauses.insert(0, "current_course_id = ?")
            params.insert(0, new_cid)
        if new_lid != lid:
            set_clauses.insert(0, "current_lecture_id = ?")
            params.insert(0, new_lid)
        if "mode" in updates:
            set_clauses.append("revision_mode = ?")
            params.append(updates["mode"])
        set_clauses.append("history = ?")
        params.append(json.dumps(history))
        params.append(user_id)

        self.conn.execute(
            f"UPDATE conversation_sessions SET {', '.join(set_clauses)} WHERE user_id = ?",
            params
        )

        if "reminder" in updates:
            self.create_reminder(
                user_id, updates["reminder"],
                updates.get("course_title", ""),
                updates.get("lecture_title", ""),
                reminder_at=updates.get("reminder_at")
            )
        if "preferences" in updates:
            for key, value in updates["preferences"]:
                self.conn.execute(
                    """INSERT INTO user_preferences (user_id, pref_key, pref_value)
                       VALUES (?, ?, ?) ON CONFLICT(user_id, pref_key)
                       DO UPDATE SET pref_value = ?, updated_at = CURRENT_TIMESTAMP""",
                    (user_id, key, value, value)
                )
        if "words" in updates:
            for word_data in updates["words"]:
                self.add_word(
                    user_id,
                    word_data.get("word", ""),
                    word_data.get("meaning", ""),
                    word_data.get("example", ""),
                    new_cid or cid,
                    new_lid or lid,
                )
        if "notes" in updates:
            for note_data in updates["notes"]:
                self.add_note(
                    user_id,
                    note_data.get("topic", ""),
                    note_data.get("content", ""),
                    new_cid or cid,
                )
