import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
import re
from typing import Optional
from .models_postgres import ALL_TABLES


class Database:
    def __init__(self):
        dsn = os.environ["DATABASE_URL"]
        if "sslmode=" not in dsn and not re.search(r'@localhost[:/]', dsn):
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}sslmode=require"
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True
        self._init_tables()

    def _init_tables(self):
        with self.conn.cursor() as cur:
            for stmt in ALL_TABLES:
                cur.execute(stmt)

    def _row_to_dict(self, row):
        return dict(row) if row else None

    # -- Courses --
    def create_course(self, title: str, user_id: int) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO courses (title, user_id) VALUES (%s, %s) RETURNING *",
                (title, user_id)
            )
            return dict(cur.fetchone())

    def get_courses(self, user_id: int) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM courses WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_course(self, course_id: int) -> Optional[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
            return self._row_to_dict(cur.fetchone())

    def find_course_by_title(self, title: str, user_id: int) -> Optional[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM courses WHERE LOWER(title) = LOWER(%s) AND user_id = %s",
                (title, user_id)
            )
            return self._row_to_dict(cur.fetchone())

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
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO lectures
                   (course_id, title, summary, key_concepts, important_equations,
                    common_misconceptions, compressed_knowledge)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (course_id, title, summary, key_concepts, important_equations,
                 common_misconceptions, compressed_knowledge)
            )
            return dict(cur.fetchone())

    def get_lectures(self, course_id: int) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM lectures WHERE course_id = %s ORDER BY created_at DESC",
                (course_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_lecture(self, lecture_id: int) -> Optional[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM lectures WHERE id = %s", (lecture_id,))
            return self._row_to_dict(cur.fetchone())

    def find_lecture_by_title(self, course_id: int, title: str) -> Optional[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM lectures WHERE course_id = %s AND LOWER(title) = LOWER(%s)",
                (course_id, title)
            )
            return self._row_to_dict(cur.fetchone())

    def find_or_create_lecture(self, course_id: int, title: str) -> dict:
        lecture = self.find_lecture_by_title(course_id, title)
        if lecture:
            return lecture
        return self.create_lecture(course_id, title)

    def get_recent_lectures(self, user_id: int, limit: int = 5) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT l.*, c.title as course_title
                   FROM lectures l
                   JOIN courses c ON c.id = l.course_id
                   WHERE c.user_id = %s
                   ORDER BY l.created_at DESC LIMIT %s""",
                (user_id, limit)
            )
            return [dict(r) for r in cur.fetchall()]

    # -- Lecture Sources --
    def add_lecture_source(self, lecture_id: int, filename: str,
                           original_text: str, file_type: str) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO lecture_sources (lecture_id, filename, original_text, file_type) VALUES (%s, %s, %s, %s) RETURNING *",
                (lecture_id, filename, original_text, file_type)
            )
            return dict(cur.fetchone())

    def get_lecture_sources(self, lecture_id: int) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM lecture_sources WHERE lecture_id = %s",
                (lecture_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    # -- Questions --
    def create_question(self, lecture_id: int, question_type: str,
                        question_text: str, answer_text: str = None,
                        difficulty: int = 1) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO questions
                   (lecture_id, question_type, question_text, answer_text, difficulty)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (lecture_id, question_type, question_text, answer_text, difficulty)
            )
            return dict(cur.fetchone())

    def get_questions_by_lecture(self, lecture_id: int, qtype: str = None) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if qtype:
                cur.execute(
                    "SELECT * FROM questions WHERE lecture_id = %s AND question_type = %s",
                    (lecture_id, qtype)
                )
            else:
                cur.execute(
                    "SELECT * FROM questions WHERE lecture_id = %s",
                    (lecture_id,)
                )
            return [dict(r) for r in cur.fetchall()]

    def get_question(self, question_id: int) -> Optional[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
            return self._row_to_dict(cur.fetchone())

    # -- Reminders --
    def create_reminder(self, user_id: int, content: str,
                        course: str = None, lecture: str = None,
                        reminder_at: str = None) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if reminder_at:
                cur.execute(
                    """INSERT INTO reminders (user_id, content, course, lecture, next_review_at)
                       VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                    (user_id, content, course, lecture, reminder_at)
                )
            else:
                cur.execute(
                    """INSERT INTO reminders (user_id, content, course, lecture, next_review_at)
                       VALUES (%s, %s, %s, %s, NOW() + INTERVAL '1 day') RETURNING *""",
                    (user_id, content, course, lecture)
                )
            return dict(cur.fetchone())

    def get_due_reminders(self, user_id: int) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM reminders WHERE user_id = %s AND next_review_at <= NOW() ORDER BY next_review_at",
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_all_users_with_due_reminders(self) -> list[int]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT DISTINCT user_id FROM reminders WHERE next_review_at <= NOW()"
            )
            return [r["user_id"] for r in cur.fetchall()]

    def update_reminder_schedule(self, reminder_id: int, correct: bool):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM reminders WHERE id = %s", (reminder_id,)
            )
            reminder = cur.fetchone()
            if not reminder:
                return
            r = dict(reminder)
            if correct:
                new_interval = r["interval_days"] * 2.0
                new_reps = r["repetitions"] + 1
            else:
                new_interval = 1.0
                new_reps = 0
            cur.execute(
                "UPDATE reminders SET interval_days = %s, repetitions = %s, next_review_at = NOW() + (%s * INTERVAL '1 day') WHERE id = %s",
                (new_interval, new_reps, new_interval, reminder_id)
            )

    # -- Performance Tracking --
    def record_answer(self, user_id: int, question_id: int = None,
                      lecture_id: int = None, course_id: int = None,
                      topic: str = None, correct: bool = None,
                      confidence: int = None):
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO performance_tracking
                   (user_id, question_id, lecture_id, course_id, topic, correct, confidence)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, question_id, lecture_id, course_id, topic, correct, confidence)
            )

    def get_weak_topics(self, user_id: int) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT topic, COUNT(*) as attempts,
                          SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END) as mistakes,
                          ROUND(AVG(confidence), 1) as avg_confidence
                   FROM performance_tracking
                   WHERE user_id = %s AND topic IS NOT NULL
                   GROUP BY topic
                   HAVING SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END) > 0 OR AVG(confidence) < 3
                   ORDER BY mistakes DESC, avg_confidence ASC
                   LIMIT 10""",
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_performance_summary(self, user_id: int) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(*) as c FROM performance_tracking WHERE user_id = %s",
                (user_id,)
            )
            total = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) as c FROM performance_tracking WHERE user_id = %s AND correct = 1",
                (user_id,)
            )
            correct = cur.fetchone()
        weak = self.get_weak_topics(user_id)
        return {
            "total_attempts": total["c"] if total else 0,
            "correct": correct["c"] if correct else 0,
            "weak_topics": [w["topic"] for w in weak],
        }

    # -- User Preferences --
    def set_preference(self, user_id: int, key: str, value: str):
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_preferences (user_id, pref_key, pref_value)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, pref_key)
                   DO UPDATE SET pref_value = %s, updated_at = CURRENT_TIMESTAMP""",
                (user_id, key, value, value)
            )

    def get_preferences(self, user_id: int) -> list[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT pref_key, pref_value FROM user_preferences WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_preferences_as_text(self, user_id: int) -> str:
        prefs = self.get_preferences(user_id)
        if not prefs:
            return "none"
        return "; ".join(f"{p['pref_key']}: {p['pref_value']}" for p in prefs)

    # -- Conversation Sessions --
    def get_active_session(self, user_id: int) -> Optional[dict]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM conversation_sessions WHERE user_id = %s",
                (user_id,)
            )
            return self._row_to_dict(cur.fetchone())

    def get_or_create_session(self, user_id: int) -> dict:
        session = self.get_active_session(user_id)
        if session:
            return session
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO conversation_sessions (user_id) VALUES (%s) RETURNING *",
                (user_id,)
            )
            return dict(cur.fetchone())

    def update_session(self, user_id: int, **kwargs):
        fields = []
        values = []
        for key, val in kwargs.items():
            if key in ("current_course_id", "current_lecture_id", "revision_mode", "history", "active"):
                fields.append(f"{key} = %s")
                if isinstance(val, (list, dict)):
                    values.append(json.dumps(val))
                else:
                    values.append(val)
        if fields:
            values.append(user_id)
            with self.conn.cursor() as cur:
                cur.execute(
                    f"UPDATE conversation_sessions SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                    values
                )

    def add_to_history(self, user_id: int, role: str, text: str, max_history: int = 20):
        session = self.get_or_create_session(user_id)
        history = json.loads(session.get("history", "[]"))
        history.append({"role": role, "text": text})
        if len(history) > max_history:
            history = history[-max_history:]
        self.update_session(user_id, history=json.dumps(history))

    def end_session(self, user_id: int):
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversation_sessions WHERE user_id = %s",
                (user_id,)
            )

    # -- Consolidated chat context --
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
            set_clauses.insert(0, "current_course_id = %s")
            params.insert(0, new_cid)
        if new_lid != lid:
            set_clauses.insert(0, "current_lecture_id = %s")
            params.insert(0, new_lid)
        if "mode" in updates:
            set_clauses.append("revision_mode = %s")
            params.append(updates["mode"])
        set_clauses.append("history = %s")
        params.append(json.dumps(history))
        params.append(user_id)

        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE conversation_sessions SET {', '.join(set_clauses)} WHERE user_id = %s",
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
            with self.conn.cursor() as cur:
                for key, value in updates["preferences"]:
                    cur.execute(
                        """INSERT INTO user_preferences (user_id, pref_key, pref_value)
                           VALUES (%s, %s, %s) ON CONFLICT (user_id, pref_key)
                           DO UPDATE SET pref_value = %s, updated_at = CURRENT_TIMESTAMP""",
                        (user_id, key, value, value)
                    )
