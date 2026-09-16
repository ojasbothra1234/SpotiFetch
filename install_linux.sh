#!/usr/bin/env bash

# SpotiFetch 100% Non-Root / No-Sudo Linux Installer
# Installs everything directly in user space without requiring root/sudo privileges

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  🚀 Installing SpotiFetch for Linux (No Sudo Required)"
echo "========================================================"
echo ""

# Find Python 3
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "❌ Error: Python is not found."
    echo "Please ensure Python 3 is installed or available in your user environment."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Found Python $PYTHON_VERSION ($PYTHON)"

# Create local Python virtual environment without sudo
mkdir -p bin downloads "$HOME/.spotdl"

echo ""
echo "🐍 Setting up Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    if "$PYTHON" -m venv .venv 2>/dev/null; then
        echo "✅ Virtual environment created."
    else
        echo "⚠️ python3-venv module not available. Installing directly to user site packages..."
    fi
fi

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    PIP_CMD="pip"
    RUN_PYTHON="python"
else
    PIP_CMD="$PYTHON -m pip install --user"
    RUN_PYTHON="$PYTHON"
fi

# Upgrade pip & install SpotiFetch requirements
echo "📦 Installing Python packages from requirements.txt..."
$PIP_CMD install --upgrade pip 2>/dev/null || true
$PIP_CMD install -r requirements.txt

# Install portable FFmpeg into ~/.spotdl without sudo if missing
echo ""
echo "🎬 Checking FFmpeg availability..."
if command -v ffmpeg &>/dev/null; then
    echo "✅ System FFmpeg detected: $(command -v ffmpeg)"
elif [ -f "$HOME/.spotdl/ffmpeg" ] || [ -f "./bin/ffmpeg" ]; then
    echo "✅ Portable FFmpeg detected."
else
    echo "⬇️ Downloading portable FFmpeg to ~/.spotdl (no root needed)..."
    $RUN_PYTHON -m spotdl --download-ffmpeg || {
        echo "⚠️ SpotDL auto-download failed. Trying direct static download..."
        ARCH=$(uname -m)
        if [ "$ARCH" = "x86_64" ]; then
            curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg-static.tar.xz 2>/dev/null && \
            tar -xf /tmp/ffmpeg-static.tar.xz -C /tmp && \
            cp /tmp/ffmpeg-*-static/ffmpeg "$HOME/.spotdl/ffmpeg" 2>/dev/null && \
            chmod +x "$HOME/.spotdl/ffmpeg" 2>/dev/null || true
            rm -rf /tmp/ffmpeg-* 2>/dev/null || true
        fi
    }
fi

# Install portable Deno into ~/.spotdl without sudo
echo "⚡ Downloading Deno runtime for YouTube extraction (no root needed)..."
$RUN_PYTHON -m spotdl --download-deno 2>/dev/null || true

# Make shell scripts executable
chmod +x start.sh install_linux.sh 2>/dev/null || true

echo ""
echo "========================================================"
echo "  ✅ SpotiFetch Installation Complete! (100% User Space)"
echo "========================================================"
echo "To run SpotiFetch, simply run:"
echo "   ./start.sh"
echo ""
echo "Or run manually:"
echo "   python3 main.py"
echo "========================================================"
