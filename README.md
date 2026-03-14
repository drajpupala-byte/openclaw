# OpenClaw

A Telegram bot powered by [Claude](https://claude.ai) (Anthropic), designed to run as a persistent service on a Mac mini.

## Features

- Multi-turn conversations with per-user history
- Streaming responses from Claude
- `/reset` to clear conversation history per user
- Automatic restart via macOS launchd (runs on login, survives crashes)
- Configurable model, token limits, and system prompt

## Quick Start

### Prerequisites

| Requirement | How to get it |
|---|---|
| Python 3.11+ | [python.org](https://python.org) or `brew install python` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Telegram bot token | Message [@BotFather](https://t.me/BotFather) on Telegram |

### 1. Clone and configure

```bash
git clone <repo-url> openclaw
cd openclaw
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN
```

### 2. Run setup (Mac mini)

```bash
bash setup.sh
```

This script:
1. Creates a Python virtual environment (`.venv/`)
2. Installs all dependencies
3. Creates `.env` from the example template (if not already present)
4. Installs and starts a **launchd** service that runs automatically on login

### 3. Add your API keys

```bash
nano .env   # or open with any text editor
```

Fill in:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456789:ABC...
```

### 4. Restart the service

```bash
launchctl unload ~/Library/LaunchAgents/com.openclaw.bot.plist
launchctl load   ~/Library/LaunchAgents/com.openclaw.bot.plist
```

Your bot is now live on Telegram!

---

## Running manually (without launchd)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys
python bot.py
```

---

## Configuration

All settings live in `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Telegram bot token from @BotFather |
| `MAX_HISTORY_TURNS` | No | `20` | Conversation turns kept per user |
| `MAX_TOKENS` | No | `4096` | Max tokens per Claude response |
| `SYSTEM_PROMPT` | No | (see bot.py) | Custom personality/instructions |

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Show commands and model info |
| `/reset` | Clear your conversation history |

---

## Logs (Mac mini service)

```bash
# Live output
tail -f /tmp/openclaw.log

# Live errors
tail -f /tmp/openclaw.err
```

---

## Uninstall service

```bash
launchctl unload ~/Library/LaunchAgents/com.openclaw.bot.plist
rm ~/Library/LaunchAgents/com.openclaw.bot.plist
```

---

## Project structure

```
openclaw/
├── bot.py                    # Main bot
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── com.openclaw.bot.plist    # macOS launchd service definition
├── setup.sh                  # One-command setup for Mac mini
└── README.md
```
