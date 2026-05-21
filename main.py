import os
import sys
import argparse
import logging
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN as CFG_TOKEN, WEBHOOK_URL as CFG_WEBHOOK, PORT as CFG_PORT
from database.db import Database
from ai.gemini_client import GeminiClient
from bot.handlers import BotHandlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_override_token = ""
_override_webhook = ""

db = Database()
ai = GeminiClient()
handlers = BotHandlers(db, ai)
ptb_app: Application = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app
    logger.info("Starting up...")

    token = os.getenv("TELEGRAM_BOT_TOKEN") or _override_token or CFG_TOKEN
    webhook = os.getenv("WEBHOOK_URL") or _override_webhook or CFG_WEBHOOK

    if token:
        ptb_app = Application.builder().token(token).build()

        ptb_app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, handlers.handle_message
        ))
        ptb_app.add_handler(MessageHandler(
            filters.PHOTO, handlers.handle_photo
        ))
        ptb_app.add_handler(MessageHandler(
            filters.Document.ALL, handlers.handle_document
        ))

        await ptb_app.initialize()
        await ptb_app.start()

        if webhook:
            webhook_url = f"{webhook.rstrip('/')}/webhook"
            await ptb_app.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.error("No TELEGRAM_BOT_TOKEN provided.")

    logger.info("Startup complete.")
    yield

    if ptb_app:
        await ptb_app.stop()
        await ptb_app.shutdown()


app = FastAPI(title="Study Companion Bot", lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request):
    global ptb_app
    if not ptb_app:
        return {"error": "Bot not initialized"}, 503
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"error": str(e)}, 500


@app.get("/health")
async def health():
    return {"status": "ok", "bot_ready": ptb_app is not None}


@app.get("/")
async def root():
    return {"message": "Study Companion Bot is running."}


def main():
    global _override_webhook

    parser = argparse.ArgumentParser(description="Study Companion Bot")
    parser.add_argument("--webhook-url", help="Webhook URL, e.g. https://your-app.onrender.com")
    parser.add_argument("--port", type=int, default=CFG_PORT, help="Port to listen on")
    args, _ = parser.parse_known_args()

    if args.webhook_url:
        _override_webhook = args.webhook_url

    port = args.port or CFG_PORT
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
