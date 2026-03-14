#!/usr/bin/env bash
# setup.sh – One-time setup for OpenClaw on macOS (Mac mini)
# Usage: bash setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PLIST_SRC="$SCRIPT_DIR/com.openclaw.bot.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.openclaw.bot.plist"

echo "=== OpenClaw Setup ==="
echo ""

# ── 1. Python check ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install it from https://python.org" >&2
  exit 1
fi
PYTHON=$(command -v python3)
echo "[1/5] Python found: $PYTHON ($(python3 --version))"

# ── 2. Virtual environment ────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "[2/5] Creating virtual environment at $VENV_DIR …"
  python3 -m venv "$VENV_DIR"
else
  echo "[2/5] Virtual environment already exists at $VENV_DIR"
fi
VENV_PYTHON="$VENV_DIR/bin/python"

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo "[3/5] Installing Python dependencies …"
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "      Done."

# ── 4. .env file ──────────────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "[4/5] Creating .env from .env.example – fill in your API keys!"
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
else
  echo "[4/5] .env already exists – skipping."
fi

# ── 5. launchd service ────────────────────────────────────────────────────────
echo "[5/5] Installing launchd service …"
BOT_PY="$SCRIPT_DIR/bot.py"

# Patch the placeholder values in the plist
sed \
  -e "s|REPLACE_WITH_VENV_PYTHON_PATH|$VENV_PYTHON|g" \
  -e "s|REPLACE_WITH_BOT_PY_PATH|$BOT_PY|g" \
  -e "s|REPLACE_WITH_OPENCLAW_DIR|$SCRIPT_DIR|g" \
  "$PLIST_SRC" > "$PLIST_DST"

# Unload existing service if present (ignore errors)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "      Service registered: com.openclaw.bot"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN"
echo "  2. Restart the service:"
echo "       launchctl unload ~/Library/LaunchAgents/com.openclaw.bot.plist"
echo "       launchctl load   ~/Library/LaunchAgents/com.openclaw.bot.plist"
echo ""
echo "Logs:"
echo "  tail -f /tmp/openclaw.log"
echo "  tail -f /tmp/openclaw.err"
