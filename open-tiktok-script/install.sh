#!/bin/bash
# open-tiktok-script local install helper

set -e

SKILL_NAME="open-tiktok-script"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${CODEX_HOME:-$HOME/.codex}/skills/$SKILL_NAME"

echo "Installing $SKILL_NAME skill..."
echo ""

check_dep() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing dependency: $1"
        echo "Install: $2"
        exit 1
    fi
}

check_dep uv "curl -LsSf https://astral.sh/uv/install.sh | sh"

if ! command -v yt-dlp >/dev/null 2>&1; then
    echo "Warning: yt-dlp not found. TikTok download requires:"
    echo "  brew install yt-dlp"
    echo "  or pip install yt-dlp"
    echo ""
fi

mkdir -p "$TARGET_DIR"
rsync -a --delete \
    --exclude '.env' \
    --exclude '.git/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '_temp/' \
    "$SOURCE_DIR/" "$TARGET_DIR/"

echo "Installed to: $TARGET_DIR"
echo ""
echo "Before use:"
echo "  1. Configure VIDEO_ANALYSIS_BASE_URL if using another deployment."
echo "     For local tests, set VIDEO_ANALYSIS_ENV=local and VIDEO_ANALYSIS_API_KEY."
echo "     Production mode does not send X-API-Key."
echo "  2. Install yt-dlp if you need TikTok video downloads."
echo "  3. Restart Codex to pick up the new skill."
