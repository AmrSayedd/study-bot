import logging
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r'https?://[^\s]+', re.IGNORECASE)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._text.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._text)


def extract_urls(text: str) -> list[str]:
    return URL_REGEX.findall(text)


def fetch_url(url: str, max_chars: int = 50000) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; StudyBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        extractor = _TextExtractor()
        extractor.feed(raw)
        text = extractor.get_text()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[Content truncated...]"
        return text
    except Exception as e:
        logger.warning(f"Failed to fetch URL {url}: {e}")
        return ""
