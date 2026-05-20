"""Conversation utilities for extracting context from messages."""

import re


def extract_topic(text: str) -> str | None:
    """Try to extract a topic name from a message."""
    patterns = [
        r"(?:revise|study|review|learn about|go over|cover)\s+['\"]?(.+?)['\"]?(?:\s+today|\s*$|\.)",
        r"(?:about|regarding|on the topic of)\s+['\"]?(.+?)['\"]?(?:\s*$|\.)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_course_lecture(text: str) -> tuple[str | None, str | None]:
    """Try to extract course and lecture from a message like 'Robotics - Jacobians'."""
    patterns = [
        r"(?:course|class|subject)\s+['\"]?(.+?)['\"]?\s+(?:lecture|chapter|topic)\s+['\"]?(.+?)['\"]?",
        r"['\"]?(.+?)['\"]?\s*[–—-]\s*['\"]?(.+?)['\"]?",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None, None


def is_revision_request(text: str) -> bool:
    keywords = ["revise", "review", "study", "practice", "quiz", "test me",
                "ask me", "let's go", "i'm ready", "start revision"]
    return any(kw in text.lower() for kw in keywords)


def is_reminder_request(text: str) -> bool:
    keywords = ["remind me", "remember that", "don't forget", "save this",
                "note that", "make a note", "keep in mind"]
    return any(kw in text.lower() for kw in keywords)
