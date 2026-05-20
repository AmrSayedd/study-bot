import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "study_bot.db"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "8080"))
UPLOADS_DIR = BASE_DIR / "uploads"
GEMINI_MODEL = "gemini-1.5-flash"
MAX_HISTORY = 20
