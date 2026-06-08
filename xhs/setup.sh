#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MC_DIR="$SCRIPT_DIR/MediaCrawler"

echo "=== XHS Data Collector Setup ==="

# Check Python version
python3 -c "
import sys
v = sys.version_info
if v < (3, 11):
    print(f'Error: Python >= 3.11 required, got {v.major}.{v.minor}')
    sys.exit(1)
print(f'Python {v.major}.{v.minor}.{v.micro} OK')
"

# Check Node.js
if command -v node &>/dev/null; then
    echo "Node.js $(node -v) OK"
else
    echo "Warning: Node.js not found. Required for some platforms (not critical for XHS)."
fi

# Clone MediaCrawler
if [ -d "$MC_DIR" ]; then
    echo "MediaCrawler already exists, pulling latest..."
    git -C "$MC_DIR" pull --ff-only || echo "Pull failed, using existing version."
else
    echo "Cloning MediaCrawler..."
    git clone https://github.com/NanmiCoder/MediaCrawler.git "$MC_DIR"
fi

# Install uv if not present (required — pip fails with Python 3.13)
if ! command -v uv &>/dev/null; then
    echo "Installing uv package manager..."
    if command -v brew &>/dev/null; then
        brew install uv
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
fi

# Install dependencies
cd "$MC_DIR"
echo "Installing dependencies with uv..."
uv sync

# Install Playwright Chromium
echo "Installing Playwright Chromium..."
uv run python -m playwright install chromium

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Open Chrome with remote debugging:"
echo "     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222"
echo "  2. Log in to xiaohongshu.com in that Chrome window"
echo "  3. Run: python3 xhs/scripts/collect.py"
