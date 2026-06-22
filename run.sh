#!/bin/bash
# Replit entry point — install deps then start the dashboard
echo "Installing packages..."
pip install flask pyyaml groq edge-tts gtts Pillow requests python-dotenv pydub 2>&1 | tail -5
echo "Starting WealthFlow dashboard..."
python dashboard/app.py
