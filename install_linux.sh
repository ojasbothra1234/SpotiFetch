#!/usr/bin/env bash

# SpotiFetch 100% Non-Root / No-Sudo Linux Installer (Ubuntu 24.04 / Debian Compatible)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  🚀 Installing SpotiFetch for Linux"
echo "========================================================"
echo ""

# Find Python 3
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "❌ Error: Python is not found."
    echo "Please ensure Python 3 is installed."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Found Python $PYTHON_VERSION ($PYTHON)"

mkdir -p bin downloads "$HOME/.spotdl"

# Attempt Virtual Environment Setup
echo ""
echo "🐍 Setting up Python environment..."

# Clean up broken venv if exists
if [ -d ".venv" ] && [ ! -f ".venv/bin/activate" ]; then
    rm -rf .venv
fi

VENV_SUCCESS=false
if [ ! -d ".venv" ]; then
    if "$PYTHON" -m venv .venv 2>/dev/null && [ -f ".venv/bin/activate" ]; then
        VENV_SUCCESS=true
        echo "✅ Virtual environment (.venv) created successfully."
    else
        rm -rf .venv 2>/dev/null || true
        echo "ℹ️ python3-venv package not installed. Using user packages with --break-system-packages..."
    fi
else
    VENV_SUCCESS=true
fi

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    PIP_CMD="pip"
    RUN_PYTHON="python"
else
    # Handle Ubuntu 24.04+ externally managed environment (PEP 668)
    PIP_CMD="$PYTHON -m pip install --user --break-system-packages"
    RUN_PYTHON="$PYTHON"
fi

# Upgrade pip & install requirements
echo "📦 Installing SpotiFetch Python packages..."
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
    $RUN_PYTHON -m spotdl --download-ffmpeg 2>/dev/null || {
        echo "⚠️ SpotDL auto-download failed. Trying direct static download..."
        ARCH=$(uname -m)
        if [ "$ARCH" = "x86_64" ]; then
            curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg-static.tar.xz 2>/dev/null && \
            tar -xf /tmp/ffmpeg-static.tar.xz -C /tmp 2>/dev/null && \
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
echo "  ✅ SpotiFetch Installation Complete!"
echo "========================================================"
echo "To run SpotiFetch, simply run:"
echo "   ./start.sh"
echo ""
echo "Or run manually:"
if [ -f ".venv/bin/activate" ]; then
    echo "   source .venv/bin/activate && python3 main.py"
else
    echo "   python3 main.py"
fi
echo "========================================================"
