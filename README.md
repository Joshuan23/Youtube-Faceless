# WealthFlow – Faceless YouTube Channel Automation

Automated pipeline to produce, SEO-optimize, and upload faceless YouTube videos targeting **$10,000/month** in AdSense revenue.

## How It Works

```
Topic Discovery → Script (Claude AI) → Voiceover (ElevenLabs) → Video Assembly (MoviePy)
    → Thumbnail (Pillow) → SEO Metadata (Claude AI) → YouTube Upload → Analytics
```

## Revenue Path to $10k/Month

| Niche | Avg CPM | Views/Month Needed | Videos Needed |
|-------|---------|-------------------|---------------|
| Personal Finance | $18 | 555,000 | ~100 published |
| AI / Tech | $12 | 833,000 | ~150 published |
| Business | $15 | 667,000 | ~120 published |

**Strategy:** Post 5 videos/week → 100 videos in 4 months → grow to $10k via compounding.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/joshuan23/youtube-faceless
cd youtube-faceless
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env with your keys
```

Required API keys:
- **`ANTHROPIC_API_KEY`** – Claude AI for scripts & SEO ([get one](https://console.anthropic.com))
- **`ELEVENLABS_API_KEY`** – Professional voiceover ([free tier available](https://elevenlabs.io))
- **`PEXELS_API_KEY`** – Free stock footage ([get one](https://www.pexels.com/api))
- **YouTube OAuth** – See setup below

### 3. YouTube OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **YouTube Data API v3**
3. Create OAuth 2.0 credentials → Download as `credentials/client_secrets.json`
4. First run will open a browser for authorization

### 4. Run Your First Video

```bash
# Generate 1 video (dry run - script only, no render)
python main.py produce --dry-run

# Generate + render + upload (full pipeline)
python main.py produce --topic "7 passive income ideas that actually work"

# Batch produce 5 videos
python main.py produce --count 5 --niche personal_finance

# See trending topic ideas
python main.py topics --niche personal_finance
```

### 5. Start the Dashboard

```bash
python main.py dashboard
# → Open http://localhost:5000
```

### 6. Enable Auto-Posting

```bash
# Posts 1 video/day at 3 PM UTC automatically
python main.py schedule --niche personal_finance
```

---

## Commands

| Command | Description |
|---------|-------------|
| `python main.py produce` | Produce & upload a video |
| `python main.py produce --count 5` | Batch produce 5 videos |
| `python main.py produce --dry-run` | Script + SEO only |
| `python main.py topics` | List trending topic ideas |
| `python main.py thumbnail "Title Here"` | Generate thumbnail variants |
| `python main.py schedule` | Start auto-posting scheduler |
| `python main.py analytics` | Show revenue stats & projection |
| `python main.py status` | Show video pipeline status |
| `python main.py dashboard` | Launch web dashboard |

---

## Configuration

Edit `config.yaml` to customize:
- **Niche** (`personal_finance`, `ai_tech`, `business`, `health`)
- **Upload schedule** (`daily`, `5x_week`, `3x_week`)
- **Video length target** (affects ad revenue — 12 min = mid-roll ads)
- **Visual style** (colors, fonts, thumbnail design)

---

## Project Structure

```
Youtube-Faceless/
├── main.py                 # CLI entry point
├── config.yaml             # Channel configuration
├── requirements.txt
├── src/
│   ├── pipeline.py         # Main orchestration
│   ├── script_generator.py # Claude-powered scripts
│   ├── voiceover.py        # ElevenLabs / OpenAI / gTTS
│   ├── video_creator.py    # MoviePy video assembly
│   ├── thumbnail.py        # Pillow thumbnail generation
│   ├── seo.py              # SEO titles/descriptions/tags
│   ├── uploader.py         # YouTube Data API v3
│   ├── scheduler.py        # Content calendar
│   ├── analytics.py        # Revenue tracking & projection
│   ├── topics.py           # Trending topic discovery
│   └── database.py         # SQLite data layer
├── dashboard/
│   ├── app.py              # Flask dashboard
│   └── templates/index.html
├── output/                 # Generated content (gitignored)
│   ├── scripts/
│   ├── audio/
│   ├── videos/
│   └── thumbnails/
├── assets/
│   ├── fonts/              # Drop .ttf fonts here
│   └── music/              # Drop royalty-free .mp3 here
└── credentials/            # YouTube OAuth (gitignored)
```

---

## Adding Background Music

Drop royalty-free MP3 files into `assets/music/`. The video creator will randomly select one per video. Good sources:
- [YouTube Audio Library](https://studio.youtube.com/channel/*/music)
- [Pixabay Music](https://pixabay.com/music/)
- [Free Music Archive](https://freemusicarchive.org)

---

## TTS Providers (in priority order)

1. **ElevenLabs** (best quality, ~$5/month for 30k chars) — set `ELEVENLABS_API_KEY`
2. **OpenAI TTS** (good quality, ~$15/1M chars) — set `OPENAI_API_KEY`
3. **gTTS** (free, robotic voice) — no key needed, auto-fallback

---

## Monetization Timeline

```
Month 1-2:  Build catalog (40-80 videos) — $0-$100
Month 3-4:  Reach 1,000 subs + 4k watch hours (monetization threshold)
Month 5-6:  $500-$2,000/month
Month 7-9:  $2,000-$5,000/month
Month 10-12: $5,000-$10,000/month
Year 2+:    $10,000-$30,000/month (compound growth)
```

Key levers: niche CPM × views × video count × CTR × watch time.
