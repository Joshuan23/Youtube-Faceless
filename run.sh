#!/bin/bash
# Replit entry point — install deps then start the dashboard
echo "Pulling latest code..."
git pull origin claude/faceless-youtube-channel-jzncg0 2>/dev/null || true
echo "Installing system ffmpeg..."
apt-get install -y ffmpeg 2>/dev/null || true
echo "Installing base packages..."
pip install flask pyyaml groq edge-tts gtts Pillow requests python-dotenv pydub 2>&1 | tail -3
echo "Installing video packages..."
pip install moviepy imageio-ffmpeg 2>&1 | tail -3
echo "Installing YouTube packages..."
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib 2>&1 | tail -3
echo "Starting WealthFlow dashboard..."
python dashboard/app.py
