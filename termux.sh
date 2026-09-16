#!/data/data/com.termux/files/usr/bin/bash

# ==============================================================================
# 🎵 SpotiFetch - Termux (Android) 1-Click Setup & Launcher
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

clear
echo "========================================================"
echo "  🎵 SpotiFetch - Spotify Media Downloader (Termux)"
echo "========================================================"
echo ""

# 1. Check and install essential Termux packages
echo "📱 Checking Termux environment & dependencies..."

PACKAGES_TO_INSTALL=""

for pkg in python ffmpeg clang libffi openssl curl; do
    if ! command -v "$pkg" &>/dev/null && [ ! -f "$PREFIX/bin/$pkg" ]; then
        PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $pkg"
    fi
done

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "📦 Installing missing Termux packages:$PACKAGES_TO_INSTALL ..."
    pkg update -y || apt-get update -y
    pkg install -y $PACKAGES_TO_INSTALL || apt-get install -y $PACKAGES_TO_INSTALL
fi

# 2. Check and upgrade pip
echo ""
echo "🐍 Verifying Python packages..."
python -m pip install --upgrade pip setuptools wheel 2>/dev/null || true

# 3. Install SpotiFetch requirements
echo "📦 Installing SpotiFetch Python requirements..."
python -m pip install -r requirements.txt

# 4. Create local directories
mkdir -p downloads bin

# 5. Set environment variables
export HOST="0.0.0.0"
export PORT="8000"
export PATH="$PREFIX/bin:$SCRIPT_DIR/bin:$HOME/.spotdl:$PATH"

echo ""
echo "========================================================"
echo "  🚀 SpotiFetch is Starting on Android!"
echo "========================================================"
echo " 👉 Web UI: http://localhost:8000"
echo "    or:     http://127.0.0.1:8000"
echo "========================================================"
echo ""

# 6. Auto-open browser on Android (using native Android intent)
echo "🌐 Launching your phone browser..."
(
    sleep 2
    if command -v termux-open-url &>/dev/null; then
        termux-open-url "http://localhost:8000" &>/dev/null || true
    elif command -v am &>/dev/null; then
        am start -a android.intent.action.VIEW -d "http://localhost:8000" &>/dev/null || true
    fi
) &

# 7. Start SpotiFetch server
exec python main.py
