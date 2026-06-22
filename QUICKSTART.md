# Quickstart – Faceless YouTube Channel

Follow these 6 steps in order. Each one takes 5 minutes or less.

---

## Before You Start

Install Python 3.10+ and ffmpeg, then run:
```bash
pip install -r requirements.txt
cp .env.example .env
```

---

## Step 1 – Get your Claude API key (free $5 credit)

1. Go to **https://console.anthropic.com**
2. Sign up → click "Get API Keys" → Create key
3. Open `.env` and paste it:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
   ```

Test it works:
```bash
python start.py step1
```
You'll see 10 topic ideas. Done.

---

## Step 2 – Write a script

```bash
python start.py step2
```

Claude writes a full 12-minute script + SEO title/tags.
Output saved to `output/scripts/`.

To use your own topic, edit `start.py` line 22:
```python
TOPIC = "7 passive income ideas that actually work"
```

---

## Step 3 – Make the voiceover

**Free option (robotic voice):** just run it — gTTS is the fallback.
```bash
python start.py step3
```

**Better voice (natural, free tier):**
1. Sign up at **https://elevenlabs.io** (free = 10k chars/month)
2. Get API key from Profile → API Keys
3. Add to `.env`:
   ```
   ELEVENLABS_API_KEY=xxxxxxxxxxxxxxxx
   ```

Output saved to `output/audio/`.

---

## Step 4 – Build the video

Requires **ffmpeg** on your system:
- Mac: `brew install ffmpeg`
- Ubuntu: `sudo apt install ffmpeg`
- Windows: download from https://ffmpeg.org

```bash
python start.py step4
```

Takes 1–3 minutes. Output saved to `output/videos/`.

**Want better visuals?**  
Add free stock footage:
1. Get a free key at **https://www.pexels.com/api**
2. Add to `.env`: `PEXELS_API_KEY=xxxxxxxx`

---

## Step 5 – Create thumbnail

```bash
python start.py step5
```

Generates 3 thumbnail variants in `output/thumbnails/`.
Open them and pick the best looking one.

---

## Step 6 – Upload to YouTube

**First-time setup (one time only):**
1. Go to **https://console.cloud.google.com**
2. Create a new project
3. Search "YouTube Data API v3" → Enable it
4. Go to Credentials → Create → OAuth 2.0 Client ID → Desktop App
5. Download the JSON → save as `credentials/client_secrets.json`

```bash
python start.py step6
```

First run opens your browser to authorize. After that it's automatic.

---

## Run everything at once

Once all keys are set up:
```bash
python start.py all
```

---

## Automate daily posting

```bash
python main.py schedule
```

Runs every day at 3 PM UTC, picks a trending topic, and posts automatically.

---

## Watch your revenue

```bash
python main.py dashboard
```

Open **http://localhost:5000** to see your revenue dashboard and $10k projection.

---

## Cost breakdown

| Tool | Cost | Notes |
|------|------|-------|
| Claude API | ~$0.10/video | Script + SEO generation |
| ElevenLabs | Free–$5/mo | 10k chars free, then $5/mo |
| Pexels | Free | Unlimited stock footage |
| YouTube API | Free | 10,000 units/day free |
| **Total** | **~$0.10–$5/video** | |

At $0.10/video × 5 videos/week = ~$2/week to run.

---

## What niche should I pick?

| Niche | Avg CPM | Difficulty |
|-------|---------|-----------|
| Personal Finance | $15–$25 | Medium |
| AI & Tech | $10–$15 | Easy |
| Business | $12–$20 | Medium |
| Health | $8–$12 | Easy |

Change your niche in `start.py` line 21:
```python
NICHE = "personal_finance"
```
