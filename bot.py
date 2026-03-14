#!/usr/bin/env python3
"""
OpenClaw – Telegram bot powered by Claude (Anthropic) with X/Twitter integration.
Designed to run as a persistent service on a Mac mini.

Telegram commands:
  /start        – welcome message
  /help         – show all commands
  /reset        – clear conversation history

  /tweet <text> – post a tweet
  /mentions     – read & reply to recent mentions with Claude
  /dms          – read & reply to recent DMs with Claude
  /search <q>   – search tweets and summarise with Claude
  /timeline     – summarise your home timeline with Claude
"""

import logging
import os
import textwrap
from collections import defaultdict

import tweepy
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
X_API_KEY           = os.environ["X_API_KEY"]
X_API_SECRET        = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN      = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]
X_BEARER_TOKEN      = os.environ["X_BEARER_TOKEN"]

MODEL             = "claude-opus-4-6"
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))
MAX_TOKENS        = int(os.getenv("MAX_TOKENS", "4096"))
SYSTEM_PROMPT     = os.getenv(
    "SYSTEM_PROMPT",
    "You are Claude, a helpful AI assistant made by Anthropic. "
    "Be concise and friendly. Format responses in plain text (no Markdown).",
)
TELEGRAM_MAX_CHARS = 4096

# ── Clients ───────────────────────────────────────────────────────────────────

anthropic = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# Tweepy v2 client (read + write + DMs)
twitter = tweepy.Client(
    bearer_token=X_BEARER_TOKEN,
    consumer_key=X_API_KEY,
    consumer_secret=X_API_SECRET,
    access_token=X_ACCESS_TOKEN,
    access_token_secret=X_ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True,
)

# ── State ─────────────────────────────────────────────────────────────────────

histories: dict[int, list[dict]] = defaultdict(list)

# ── Helpers ───────────────────────────────────────────────────────────────────


def trim_history(user_id: int) -> None:
    h = histories[user_id]
    max_messages = MAX_HISTORY_TURNS * 2
    if len(h) > max_messages:
        histories[user_id] = h[-max_messages:]


def split_message(text: str, limit: int = TELEGRAM_MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def ask_claude(user_id: int, user_text: str) -> str:
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
        if histories[user_id] and histories[user_id][-1]["role"] == "user":
            histories[user_id].pop()
        raise
    histories[user_id].append({"role": "assistant", "content": full_reply})
    return full_reply


async def claude_summarise(prompt: str) -> str:
    """One-shot Claude call (no history) for summarising X content."""
    response = await anthropic.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return next((b.text for b in response.content if b.type == "text"), "")


def get_my_user_id() -> str:
    me = twitter.get_me()
    return me.data.id


# ── Telegram command handlers ─────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm Claude with X/Twitter integration.\n\n"
        "Chat commands:\n"
        "  /help     – all commands\n"
        "  /reset    – clear chat history\n\n"
        "X/Twitter commands:\n"
        "  /tweet <text>  – post a tweet\n"
        "  /mentions      – read & reply to mentions\n"
        "  /dms           – read & reply to DMs\n"
        "  /search <q>    – search & summarise tweets\n"
        "  /timeline      – summarise your timeline"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    histories.pop(update.effective_user.id, None)
    await update.message.reply_text("Conversation history cleared!")


# ── X/Twitter handlers ────────────────────────────────────────────────────────


async def cmd_tweet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Post a tweet. Usage: /tweet Your tweet text here"""
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Usage: /tweet Your tweet text here")
        return
    if len(text) > 280:
        await update.message.reply_text(
            f"Tweet is too long ({len(text)} chars). Max is 280."
        )
        return
    try:
        resp = twitter.create_tweet(text=text)
        tweet_id = resp.data["id"]
        await update.message.reply_text(
            f"Tweet posted!\nhttps://twitter.com/i/web/status/{tweet_id}"
        )
    except Exception as exc:
        logger.error("Tweet error: %s", exc, exc_info=True)
        await update.message.reply_text(f"Failed to post tweet: {exc}")


async def cmd_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch recent mentions and let Claude draft replies."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    try:
        me_id = get_my_user_id()
        resp = twitter.get_users_mentions(
            id=me_id, max_results=5,
            tweet_fields=["author_id", "text", "created_at"],
        )
        if not resp.data:
            await update.message.reply_text("No recent mentions found.")
            return

        mentions_text = "\n\n".join(
            f"Tweet ID {t.id}:\n{t.text}" for t in resp.data
        )
        prompt = (
            "Here are recent mentions on X/Twitter. "
            "For each one, draft a short, friendly reply (max 280 chars):\n\n"
            + mentions_text
        )
        summary = await claude_summarise(prompt)
        for chunk in split_message(f"Recent mentions + suggested replies:\n\n{summary}"):
            await update.message.reply_text(chunk)
    except Exception as exc:
        logger.error("Mentions error: %s", exc, exc_info=True)
        await update.message.reply_text(f"Error fetching mentions: {exc}")


async def cmd_dms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch recent DMs and let Claude draft replies."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    try:
        resp = twitter.get_direct_message_events(max_results=5)
        if not resp.data:
            await update.message.reply_text("No recent DMs found.")
            return

        dms_text = "\n\n".join(
            f"DM from sender {dm.sender_id}:\n{dm.text}"
            for dm in resp.data
            if hasattr(dm, "text")
        )
        if not dms_text:
            await update.message.reply_text("No DM text found.")
            return

        prompt = (
            "Here are recent X/Twitter DMs. "
            "For each one, draft a short, helpful reply (max 280 chars):\n\n"
            + dms_text
        )
        summary = await claude_summarise(prompt)
        for chunk in split_message(f"Recent DMs + suggested replies:\n\n{summary}"):
            await update.message.reply_text(chunk)
    except Exception as exc:
        logger.error("DMs error: %s", exc, exc_info=True)
        await update.message.reply_text(f"Error fetching DMs: {exc}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search tweets and summarise. Usage: /search <query>"""
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /search <query>")
        return
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    try:
        resp = twitter.search_recent_tweets(
            query=query, max_results=10,
            tweet_fields=["author_id", "text", "created_at"],
        )
        if not resp.data:
            await update.message.reply_text(f"No tweets found for: {query}")
            return

        tweets_text = "\n\n".join(f"- {t.text}" for t in resp.data)
        prompt = (
            f'Here are recent tweets about "{query}". '
            "Summarise the main themes, opinions, and any notable points:\n\n"
            + tweets_text
        )
        summary = await claude_summarise(prompt)
        for chunk in split_message(f'Search results for "{query}":\n\n{summary}'):
            await update.message.reply_text(chunk)
    except Exception as exc:
        logger.error("Search error: %s", exc, exc_info=True)
        await update.message.reply_text(f"Error searching tweets: {exc}")


async def cmd_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and summarise your home timeline."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    try:
        me_id = get_my_user_id()
        resp = twitter.get_home_timeline(
            max_results=10,
            tweet_fields=["author_id", "text", "created_at"],
        )
        if not resp.data:
            await update.message.reply_text("No timeline tweets found.")
            return

        tweets_text = "\n\n".join(f"- {t.text}" for t in resp.data)
        prompt = (
            "Here are recent tweets from my X/Twitter timeline. "
            "Give me a brief summary of what's happening:\n\n"
            + tweets_text
        )
        summary = await claude_summarise(prompt)
        for chunk in split_message(f"Your timeline summary:\n\n{summary}"):
            await update.message.reply_text(chunk)
    except Exception as exc:
        logger.error("Timeline error: %s", exc, exc_info=True)
        await update.message.reply_text(f"Error fetching timeline: {exc}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text
    if not user_text:
        return
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    try:
        reply = await ask_claude(user_id, user_text)
    except Exception as exc:
        logger.error("Claude error for user %s: %s", user_id, exc, exc_info=True)
        await update.message.reply_text(
            "Sorry, I hit an error talking to Claude. Please try again."
        )
        return
    for chunk in split_message(reply):
        await update.message.reply_text(chunk)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    logger.info("Starting OpenClaw bot (model=%s)", MODEL)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Chat
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))

    # X/Twitter
    app.add_handler(CommandHandler("tweet", cmd_tweet))
    app.add_handler(CommandHandler("mentions", cmd_mentions))
    app.add_handler(CommandHandler("dms", cmd_dms))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("timeline", cmd_timeline))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
