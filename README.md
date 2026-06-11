# Study Companion Bot

An AI-powered Telegram tutor that helps you learn deeply by turning your study materials into interactive revision sessions.

## Goal

Most study tools either dump information (videos, textbooks) or quiz you with generic flashcards disconnected from your actual courses. This bot bridges the gap: you upload your own lecture notes, PDFs, or images, and it generates structured revision content tailored to what you're actually studying — then quizzes you using spaced repetition and Socratic dialogue, all through a natural Telegram chat.

## Methodologies

### AI-Driven Conversational Tutoring
At the core is Google Gemini — not a fixed decision tree. The AI adapts its teaching style on the fly: it detects confusion, asks follow-up questions, and steers conversation toward weak points. State markers (COURSE, LECTURE, MODE, etc.) let the bot persist context across sessions without the AI needing to remember everything.

### Socratic Questioning
The bot is instructed to never give answers away immediately. It guides the student to discover answers themselves, which produces stronger long-term retention than passive reading.

### Multiple Revision Modes
| Mode | Purpose |
|------|---------|
| Daily | Quick active-recall questions for routine review |
| Deep | Extended Socratic discussion — "why" and "how" questions |
| Teaching | Student explains a concept; AI evaluates and fills gaps |
| Oral Exam | Strict professor-style exam with pressure follow-ups |

Each mode targets a different stage of learning, from familiarization to mastery.

### Spaced Repetition (SM-2)
Reminders use an SM-2-inspired algorithm: each successful recall doubles the interval until the next review (1d → 2d → 4d → 8d → …), while failed recalls reset to 1 day. After 5 successful pushes the reminder auto-deletes, preventing indefinite cycling of outdated material.

### Upload-Centric Organization
PDF, TXT, Markdown, and image uploads are parsed, classified into courses and lectures, then stored permanently. The AI generates summaries, key concepts, equations, and revision questions on the spot. This means you study your actual curriculum, not a generic question bank.

### Atomic Reminder Delivery
Reminders use a `try_claim_reminder` guard (atomic `UPDATE ... WHERE next_review_at <= NOW()`) so that competing delivery paths — the periodic job queue, the user's next Telegram message, and the `/wake` endpoint — never send the same reminder twice.

### Server-Side Time Handling
Users specify reminder times in local formats (HH:MM, +N minutes, HH:MM+Nd). The server converts to UTC using a stored timezone offset. This eliminates AI time-hallucination where the model would compute wrong minutes-from-now values.

### Preference System
Study preferences (e.g., "I want short answers", "English isn't my first language") are saved as key-value pairs and injected into every AI prompt. The AI adapts its behavior automatically without the user needing to repeat themselves.

## Why These Choices

**Telegram over a mobile app** — zero installation, cross-platform, and the user already has it. No app store friction.

**Uploads over pre-built content** — every course is different. Letting students upload their own lectures means the bot works for any subject without manual content curation.

**Gemini (generative AI) over traditional NLP** — rule-based bots can't handle the ambiguity of real tutoring conversations. A large language model can detect confusion, rephrase explanations, and generate novel questions from raw lecture text.

**SM-2 over fixed schedules** — decades of cognitive science research show that exponentially spaced review is far more efficient than periodic cramming. The 5-push auto-delete is a pragmatic cap to avoid reminder spam.

**Server-side time math** — large language models are notoriously bad at arithmetic. Moving timezone conversion to deterministic Python code eliminates an entire class of bugs.

**Atomic claim over simple SELECT** — Render's free tier spins down after inactivity. On wake, multiple signals (job queue, user message, /wake) race to send the same reminders. `try_claim_reminder` ensures exactly-once delivery without distributed locks or external queues.

## Tech Stack

- **Python 3.10+** — bot logic, FastAPI server
- **PostgreSQL (Supabase)** — persistence; SQLite for local dev
- **Google Gemini API** — AI conversation and content generation
- **python-telegram-bot** — Telegram bot framework
- **FastAPI + Uvicorn** — webhook server, health and wake endpoints
- **Render** — hosting (free tier with spin-down)

## Quick Start

```bash
git clone https://github.com/AmrSayedd/study-bot
cd study-bot
cp .env.example .env    # fill in TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, DATABASE_URL
pip install -r requirements-local.txt
python main.py --webhook-url=https://your-app.onrender.com
```

Send `/start` on Telegram and start chatting, uploading lectures, or asking for revision.
