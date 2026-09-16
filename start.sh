#!/usr/bin/env bash

# SpotiFetch Linux / macOS Launcher (No Sudo Required)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  🎵 Starting SpotiFetch - Spotify Media Downloader"
echo "========================================================"
echo ""

# Ensure local bin and ~/.spotdl are in user PATH
export PATH="$SCRIPT_DIR/bin:$HOME/.spotdl:$PATH"

# Find Python
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
    source .venv/bin/activate
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3 not found."
    exit 1
fi

# Check if portable ffmpeg is present in user directory if system ffmpeg is missing
if ! command -v ffmpeg &>/dev/null; then
    if [ -f "$HOME/.spotdl/ffmpeg" ]; then
        echo "✅ Using portable FFmpeg from $HOME/.spotdl/ffmpeg"
    elif [ -f "$SCRIPT_DIR/bin/ffmpeg" ]; then
        echo "✅ Using local FFmpeg from $SCRIPT_DIR/bin/ffmpeg"
    else
        echo "⚠️ FFmpeg not found. Attempting to download portable FFmpeg..."
        "$PYTHON_CMD" -m spotdl --download-ffmpeg 2>/dev/null || true
    fi
fi

# Auto-install dependencies to virtual environment or user site if missing
if ! "$PYTHON_CMD" -c "import fastapi, spotdl, uvicorn" &>/dev/null; then
    echo "📦 Dependencies missing. Running user-space install..."
    "$PYTHON_CMD" -m pip install --user -r requirements.txt 2>/dev/null || "$PYTHON_CMD" -m pip install -r requirements.txt
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "🚀 SpotiFetch is running on http://$HOST:$PORT"
echo ""

# Open default browser if desktop environment is active
if command -v xdg-open &>/dev/null && [ -n "$DISPLAY" ]; then
    (sleep 1 && xdg-open "http://$HOST:$PORT" &>/dev/null &)
elif command -v open &>/dev/null; then
    (sleep 1 && open "http://$HOST:$PORT" &>/dev/null &)
fi

exec "$PYTHON_CMD" main.py
