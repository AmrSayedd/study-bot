import os
import logging
import fitz
from config import UPLOADS_DIR

logger = logging.getLogger(__name__)


class LectureProcessor:
    @staticmethod
    def extract_text(file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return LectureProcessor._extract_pdf(file_path)
        elif ext in (".txt", ".md"):
            return LectureProcessor._extract_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        text = []
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text.append(page.get_text())
            doc.close()
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            raise
        return "\n".join(text)

    @staticmethod
    def _extract_text(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    @staticmethod
    def save_file(file_path: str, data: bytes) -> str:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        dest = os.path.join(UPLOADS_DIR, os.path.basename(file_path))
        with open(dest, "wb") as f:
            f.write(data)
        return dest
