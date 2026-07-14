# Quickstart – Twinkle Tots (Faceless Nursery Rhyme Channel)

**Completely free stack:** Groq (lyrics) + edge-tts (kid voice) + ffmpeg (video) + Pexels (clips)

---

## Setup (one time)

```bash
pip install -r requirements.txt
cp .env.example .env
```

---

## Step 1 – Get a free Groq API key (2 minutes, no credit card)

1. Go to **https://console.groq.com**
2. Sign up → click "Create API Key"
3. Open `.env` and paste it:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxx
   ```

Test it:
```bash
python start.py step1
```
You'll see 10 nursery rhyme ideas. Done.

> **Alternative:** Google Gemini is also free.
> Get a key at https://aistudio.google.com/apikey → add `GEMINI_API_KEY=...` to `.env`

---

## Step 2 – Write the lyrics (free)

```bash
python start.py step2
```

Groq (Llama 3.3 70B) writes an original nursery rhyme + kid-safe SEO metadata. Takes ~15 seconds.

To use your own topic, edit line 22 in `start.py`:
```python
TOPIC = "Twinkle Twinkle Little Star"
```

---

## Step 3 – Make the voiceover (free)

edge-tts uses Microsoft's neural voices — natural quality, completely free.

```bash
python start.py step3
```

To change the voice, edit `.env`:
```
EDGE_TTS_VOICE=en-US-AnaNeural       # child voice (default)
# EDGE_TTS_VOICE=en-US-JennyNeural   # warm female
# EDGE_TTS_VOICE=en-GB-MaisieNeural  # British child
```

> Want even better voice quality? Add `ELEVENLABS_API_KEY` to `.env`.
> Free tier at https://elevenlabs.io (10k chars/month).

---

## Step 4 – Build the video (free, needs ffmpeg)

Install ffmpeg first:
- **Mac:** `brew install ffmpeg`
- **Ubuntu:** `sudo apt install ffmpeg`
- **Windows:** download from https://ffmpeg.org

```bash
python start.py step4
```

Takes 1–3 minutes. Saves to `output/videos/`.

Want real stock footage? Get a free Pexels key at https://www.pexels.com/api and add `PEXELS_API_KEY=...` to `.env`.

---

## Step 5 – Create thumbnail (free)

```bash
python start.py step5
```

Generates 3 thumbnail variants in `output/thumbnails/`. Open them and pick the best.

---

## Step 6 – Upload to YouTube (free API)

**One-time YouTube setup:**
1. Go to **https://console.cloud.google.com**
2. New project → search "YouTube Data API v3" → Enable
3. Credentials → Create → OAuth 2.0 → Desktop App → Download JSON
4. Save as `credentials/client_secrets.json`

```bash
python start.py step6
```

First run opens your browser to authorize. After that it's fully automatic.

---

## Run everything at once

```bash
python start.py all
```

---

## Auto-post daily (free)

```bash
python main.py schedule
```

Picks a new song idea and posts every day at the configured time (default 4 PM).

---

## Dashboard (free)

```bash
python main.py dashboard
# → http://localhost:5000
```

---

## Total cost: $0

| Tool | Cost | What it does |
|------|------|-------------|
| Groq API | **Free** | Writes lyrics with Llama 3.3 70B |
| edge-tts | **Free** | Microsoft neural voice |
| Pexels API | **Free** | Stock footage |
| YouTube API | **Free** | Uploads videos |
| MoviePy | **Free** | Assembles video |
| Pillow | **Free** | Creates thumbnails |
| **Total** | **$0** | |

---

## Want to upgrade later?

| Upgrade | Cost | Benefit |
|---------|------|---------|
| ElevenLabs voice | $5/mo | Singing-quality voice |
| Claude / GPT-4 | ~$0.10/video | Slightly better lyrics |
| Pexels (already free) | $0 | — |

You can run this channel indefinitely for free. Upgrade only when you're already making money.
