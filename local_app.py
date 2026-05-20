"""
Local web UI for testing the study companion.
Reuses all the same modules: database, AI, services.
Run with: python local_app.py
Then open http://localhost:5000
"""

import os
import sys
import json
import logging
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import GEMINI_API_KEY, UPLOADS_DIR
from database.db import Database
from ai.gemini_client import GeminiClient
from services.lecture_processor import LectureProcessor
from services.revision_service import RevisionService
from services.reminder_service import ReminderService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

LOCAL_PORT = 5000
TEST_USER_ID = 1

app = FastAPI(title="Study Companion - Local Test")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

db = Database()
ai = GeminiClient()
processor = LectureProcessor()
revision_service = RevisionService(db, ai)
reminder_service = ReminderService(db)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>index.html not found in static/</h1>")


@app.get("/api/session")
async def get_session():
    session = db.get_or_create_session(TEST_USER_ID)
    course = ""
    lecture = ""
    if session.get("current_course_id"):
        c = db.get_course(session["current_course_id"])
        if c:
            course = c["title"]
    if session.get("current_lecture_id"):
        l = db.get_lecture(session["current_lecture_id"])
        if l:
            lecture = l["title"]
    weak = db.get_weak_topics(TEST_USER_ID)
    stats = db.get_performance_summary(TEST_USER_ID)
    courses = db.get_courses(TEST_USER_ID)
    return {
        "course": course,
        "lecture": lecture,
        "mode": session.get("revision_mode", "daily"),
        "weak_topics": [w["topic"] for w in weak],
        "stats": stats,
        "courses": [{"id": c["id"], "title": c["title"]} for c in courses],
    }


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    text = body.get("message", "").strip()
    if not text:
        return {"reply": "Say something!", "state": {}}

    ctx = db.get_chat_context(TEST_USER_ID)

    reminder_msg = ""
    if ctx["reminders"]:
        lines = ["📌 *Here are your pending reminders:*"]
        for r in ctx["reminders"]:
            tag = f" [{r['course']}" + (f" → {r['lecture']}]" if r["lecture"] else "]") if r["course"] else ""
            lines.append(f"• {r['content']}{tag}")
        reminder_msg = "\n".join(lines)
        for r in ctx["reminders"]:
            db.update_reminder_schedule(r["id"], True)

    response_data = ai.chat(text, ctx)
    reply = response_data["text"]
    updates = response_data["state_updates"]

    if reminder_msg:
        reply = f"{reminder_msg}\n\n{reply}"

    updates["course_title"] = ctx["course"]
    updates["lecture_title"] = ctx["lecture"]

    db.save_chat_interaction(TEST_USER_ID, text, reply, updates)

    new_course = updates.get("course", ctx["course"])
    new_lecture = updates.get("lecture", ctx["lecture"])
    new_mode = updates.get("mode", ctx["mode"])

    return {
        "reply": reply,
        "state": {"course": new_course, "lecture": new_lecture, "mode": new_mode},
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "No filename"}, status_code=400)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".txt", ".md"):
        return JSONResponse({"error": "Only PDF, TXT, MD files supported"}, status_code=400)

    try:
        content = await file.read()

        os.makedirs(UPLOADS_DIR, exist_ok=True)
        file_path = os.path.join(UPLOADS_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(content)

        extracted = processor.extract_text(file_path)

        if not extracted.strip():
            return JSONResponse({"error": "No text could be extracted"}, status_code=400)

        result = revision_service.process_upload(
            TEST_USER_ID, file_path, file.filename, extracted
        )

        reply = (
            f"✅ Processed! Added to course **{result['course']}** → "
            f"lecture **{result['lecture']}**.\n\n"
            f"{result['summary']}\n\n"
            f"Generated {result['question_count']} revision questions."
        )

        db.add_to_history(TEST_USER_ID, "user", f"[Uploaded file: {file.filename}]")
        db.add_to_history(TEST_USER_ID, "assistant", reply)

        session = db.get_or_create_session(TEST_USER_ID)
        course = ""
        lecture = ""
        if session.get("current_course_id"):
            c = db.get_course(session["current_course_id"])
            if c:
                course = c["title"]
        if session.get("current_lecture_id"):
            l = db.get_lecture(session["current_lecture_id"])
            if l:
                lecture = l["title"]

        return {
            "reply": reply,
            "state": {"course": course, "lecture": lecture, "mode": session.get("revision_mode", "daily")},
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    logger.info(f"Starting local test server on http://localhost:{LOCAL_PORT}")
    uvicorn.run("local_app:app", host="0.0.0.0", port=LOCAL_PORT, reload=True)
