#!/usr/bin/env bash
set -e

echo "=== WealthFlow Setup ==="

# Python check
python3 --version || { echo "Python 3 required"; exit 1; }

# Create venv
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "Created virtualenv"
fi

source venv/bin/activate

# Install deps
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "Dependencies installed"

# ffmpeg check (required by moviepy)
if ! command -v ffmpeg &> /dev/null; then
  echo ""
  echo "⚠  ffmpeg not found. Install it:"
  echo "   macOS:  brew install ffmpeg"
  echo "   Ubuntu: sudo apt install ffmpeg"
  echo "   Windows: https://ffmpeg.org/download.html"
fi

# Copy .env if needed
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "✓ Created .env — add your API keys"
fi

mkdir -p credentials output/scripts output/audio output/videos output/thumbnails assets/fonts assets/music

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Add API keys to .env"
echo "  2. python main.py produce --dry-run   # test script generation"
echo "  3. python main.py dashboard            # open http://localhost:5000"
