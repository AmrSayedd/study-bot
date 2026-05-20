import os
import logging
import json

logger = logging.getLogger(__name__)


class RevisionService:
    def __init__(self, db, ai):
        self.db = db
        self.ai = ai

    def get_revision_context(self, user_id: int) -> dict:
        session = self.db.get_or_create_session(user_id)
        weak = self.db.get_weak_topics(user_id)
        return {
            "course": "",
            "lecture": "",
            "mode": session.get("revision_mode", "daily"),
            "weak_topics": [w["topic"] for w in weak],
            "history": json.loads(session.get("history", "[]")),
        }

    def process_upload(self, user_id: int, file_path: str,
                       filename: str, extracted_text: str) -> dict:
        session = self.db.get_or_create_session(user_id)
        current_course_id = session.get("current_course_id")
        current_lecture_id = session.get("current_lecture_id")

        course_name = None
        lecture_name = None

        if current_course_id:
            course = self.db.get_course(current_course_id)
            if course:
                course_name = course["title"]
        if current_lecture_id:
            lecture = self.db.get_lecture(current_lecture_id)
            if lecture:
                lecture_name = lecture["title"]

        parsed = self.ai.parse_upload_intent(
            extracted_text[:2000],
            current_course=course_name or "",
            current_lecture=lecture_name or "",
        )

        course_title = parsed.get("course") or parsed.get("suggested_course") or "Untitled Course"
        lecture_title = parsed.get("lecture") or parsed.get("suggested_lecture") or "Untitled Lecture"

        course = self.db.find_or_create_course(course_title, user_id)
        lecture = self.db.find_or_create_lecture(course["id"], lecture_title)

        self.db.add_lecture_source(
            lecture["id"], filename, extracted_text,
            os.path.splitext(filename)[1].lower()
        )

        generated = self.ai.generate_lecture_content(
            lecture_title, course_title, extracted_text
        )

        self.db.create_lecture(
            course["id"], lecture_title,
            summary=generated.get("summary", ""),
            key_concepts=json.dumps(generated.get("key_concepts", [])),
            important_equations=json.dumps(generated.get("important_equations", [])),
            common_misconceptions=json.dumps(generated.get("common_misconceptions", [])),
            compressed_knowledge=extracted_text[:5000],
        )

        for q in generated.get("questions", []):
            self.db.create_question(
                lecture["id"], q.get("type", "conceptual"),
                q.get("question", ""), q.get("answer", ""),
            )

        self.db.update_session(
            user_id,
            current_course_id=course["id"],
            current_lecture_id=lecture["id"],
        )

        return {
            "course": course_title,
            "lecture": lecture_title,
            "summary": generated.get("summary", "Lecture processed."),
            "question_count": len(generated.get("questions", [])),
        }
