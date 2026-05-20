import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional
from .models import ALL_TABLES
from config import DATABASE_PATH


class Database:
    def __init__(self):
        import os
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
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
                        course: str = None, lecture: str = None) -> dict:
        cur = self.conn.execute(
            """INSERT INTO reminders (user_id, content, course, lecture, next_review_at)
               VALUES (?, ?, ?, ?, datetime('now', '+1 day'))""",
            (user_id, content, course, lecture)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def get_due_reminders(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM reminders WHERE user_id = ? AND next_review_at <= datetime('now') ORDER BY next_review_at",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

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
        cur = self.conn.execute(
            "INSERT INTO conversation_sessions (user_id) VALUES (?)",
            (user_id,)
        )
        self.conn.commit()
        return self.get_active_session(user_id)

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

    # -- Consolidated chat context (1 read call for the handler) --
    def get_chat_context(self, user_id: int) -> dict:
        session = self.get_or_create_session(user_id)
        course = ""
        lecture = ""
        if session.get("current_course_id"):
            c = self.get_course(session["current_course_id"])
            if c:
                course = c["title"]
        if session.get("current_lecture_id"):
            l = self.get_lecture(session["current_lecture_id"])
            if l:
                lecture = l["title"]
        weak = self.get_weak_topics(user_id)
        prefs = self.get_preferences_as_text(user_id)
        reminders = self.get_due_reminders(user_id)
        return {
            "session": session,
            "course": course,
            "lecture": lecture,
            "mode": session.get("revision_mode", "daily"),
            "weak_topics": [w["topic"] for w in weak],
            "preferences": prefs,
            "reminders": reminders,
            "history": json.loads(session.get("history", "[]")),
        }

    def save_chat_interaction(self, user_id: int, user_text: str,
                               reply: str, updates: dict):
        self.conn.execute("BEGIN")
        try:
            if "course" in updates:
                c = self.find_or_create_course(updates["course"], user_id)
                self.conn.execute(
                    "UPDATE conversation_sessions SET current_course_id = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (c["id"], user_id)
                )
            if "lecture" in updates:
                session = self.get_active_session(user_id)
                cid = session["current_course_id"] if session else None
                if not cid and "course" in updates:
                    c = self.find_or_create_course(updates["course"], user_id)
                    cid = c["id"]
                if cid:
                    l = self.find_or_create_lecture(cid, updates["lecture"])
                    self.conn.execute(
                        "UPDATE conversation_sessions SET current_lecture_id = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (l["id"], user_id)
                    )
            if "mode" in updates:
                self.conn.execute(
                    "UPDATE conversation_sessions SET revision_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (updates["mode"], user_id)
                )
            if "reminder" in updates:
                self.conn.execute(
                    """INSERT INTO reminders (user_id, content, course, lecture, next_review_at)
                       VALUES (?, ?, ?, ?, datetime('now', '+1 day'))""",
                    (user_id, updates["reminder"],
                     updates.get("course_title", ""),
                     updates.get("lecture_title", ""))
                )
            if "preferences" in updates:
                for key, value in updates["preferences"]:
                    self.conn.execute(
                        """INSERT INTO user_preferences (user_id, pref_key, pref_value)
                           VALUES (?, ?, ?) ON CONFLICT(user_id, pref_key)
                           DO UPDATE SET pref_value = ?, updated_at = CURRENT_TIMESTAMP""",
                        (user_id, key, value, value)
                    )

            session_data = self.get_active_session(user_id)
            history = json.loads(session_data["history"]) if session_data else []
            history.append({"role": "user", "text": user_text})
            history.append({"role": "assistant", "text": reply})
            if len(history) > 20:
                history = history[-20:]
            self.conn.execute(
                "UPDATE conversation_sessions SET history = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (json.dumps(history), user_id)
            )

            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
