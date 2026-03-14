#!/usr/bin/env python3
"""
OpenClaw – Telegram bot powered by Claude (Anthropic).
Designed to run as a persistent service on a Mac mini.
"""

import asyncio
import logging
import os
from collections import defaultdict

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

MODEL = "claude-opus-4-6"
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))  # user+assistant pairs
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are Claude, a helpful AI assistant made by Anthropic. "
    "Be concise and friendly. Format responses in plain text (no Markdown).",
)
TELEGRAM_MAX_CHARS = 4096  # Telegram message character limit

# ── State ─────────────────────────────────────────────────────────────────────

# Per-user conversation history: {user_id: [{"role": ..., "content": ...}, ...]}
histories: dict[int, list[dict]] = defaultdict(list)

anthropic = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# ── Helpers ───────────────────────────────────────────────────────────────────


def trim_history(user_id: int) -> None:
    """Keep at most MAX_HISTORY_TURNS pairs (user + assistant) in memory."""
    h = histories[user_id]
    max_messages = MAX_HISTORY_TURNS * 2
    if len(h) > max_messages:
        histories[user_id] = h[-max_messages:]


def split_message(text: str, limit: int = TELEGRAM_MAX_CHARS) -> list[str]:
    """Split long text into chunks that fit within Telegram's character limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at a newline boundary near the limit
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def ask_claude(user_id: int, user_text: str) -> str:
    """Send user_text to Claude and return the full reply."""
    histories[user_id].append({"role": "user", "content": user_text})
    trim_history(user_id)

    full_reply = ""
    try:
        async with anthropic.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=histories[user_id],
            thinking={"type": "adaptive"},
        ) as stream:
            async for text in stream.text_stream:
                full_reply += text
    except Exception:
        # Remove the user message we just appended so history stays consistent
        if histories[user_id] and histories[user_id][-1]["role"] == "user":
            histories[user_id].pop()
        raise

    histories[user_id].append({"role": "assistant", "content": full_reply})
    return full_reply


# ── Handlers ──────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm Claude, your AI assistant powered by Anthropic.\n\n"
        "Commands:\n"
        "  /help  – show this message\n"
        "  /reset – clear conversation history\n\n"
        "Just send me a message and I'll reply!"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "OpenClaw – Claude on Telegram\n\n"
        "Commands:\n"
        "  /start – welcome message\n"
        "  /help  – show this message\n"
        "  /reset – clear conversation history\n\n"
        f"Model: {MODEL}\n"
        f"Max history: {MAX_HISTORY_TURNS} turns"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    histories.pop(user_id, None)
    await update.message.reply_text("Conversation history cleared. Fresh start!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    # Show typing indicator while Claude thinks
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        reply = await ask_claude(user_id, user_text)
    except Exception as exc:
        logger.error("Claude API error for user %s: %s", user_id, exc, exc_info=True)
        await update.message.reply_text(
            "Sorry, I hit an error talking to Claude. Please try again in a moment."
        )
        return

    # Send reply, splitting into multiple messages if needed
    for chunk in split_message(reply):
        await update.message.reply_text(chunk)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    logger.info("Starting OpenClaw bot (model=%s)", MODEL)

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
