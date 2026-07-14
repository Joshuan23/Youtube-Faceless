# Twinkle Tots – Faceless Nursery Rhyme Channel Automation

Automated pipeline to write, voice, and upload **faceless nursery rhyme videos for kids** —
100% AI-generated, wholesome, and YouTube "Made for Kids" compliant.

## How It Works

```
Song idea → Lyrics (AI) → Kid-friendly voice (edge-tts) → Colorful video (ffmpeg)
    → Bright thumbnail (Pillow) → Kid-safe SEO → YouTube Upload (Made for Kids ✓)
```

Everything is faceless: no camera, no narrator on screen — just cheerful sing-along
songs with bright visuals that toddlers and preschoolers love.

## Content Styles

| Style | Category | Example songs |
|-------|----------|---------------|
| `nursery_rhymes` | Film & Animation | Twinkle Twinkle, Wheels on the Bus, Old MacDonald |
| `lullabies` | Music | Hush Little Baby, Rock-a-bye Baby, bedtime songs |
| `learning_songs` | Education | ABC Song, Counting 1–10, Colors, Shapes |

Set the default in `config.yaml` (`channel.niche`) or pick per-video in the dashboard.

---

## ⚠️ Kids Content Compliance (Important)

This project uploads every video with **`selfDeclaredMadeForKids: true`** (controlled by
`channel.made_for_kids` in `config.yaml`). This is **legally required** for children's
content under COPPA / YouTube's "Made for Kids" rules.

What this means for your channel:
- Personalized ads, comments, and some features are disabled on kids videos (by design).
- Keep every song, title, thumbnail, and description 100% wholesome and age-appropriate.
- Do **not** flip `made_for_kids` to `false` for a genuine children's channel.

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

Recommended keys (all have free tiers):
- **`GROQ_API_KEY`** – free LLM for writing lyrics ([console.groq.com](https://console.groq.com), no card)
- **edge-tts** – free, natural kid-friendly voices (no key needed, installed via requirements)
- **`PEXELS_API_KEY`** – optional colorful stock clips ([pexels.com/api](https://www.pexels.com/api))
- **YouTube OAuth** – see setup below

Optional upgrades: `ELEVENLABS_API_KEY` / `OPENAI_API_KEY` for premium voices.

### 3. YouTube OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **YouTube Data API v3**
3. Create OAuth 2.0 credentials
4. Connect from the dashboard's **/youtube-auth** page (guided flow), or drop the
   client secrets JSON into `credentials/client_secrets.json`

### 4. Make Your First Rhyme

```bash
# Just the lyrics (fast, no render, no upload)
python main.py produce --dry-run

# Full pipeline for one song
python main.py produce --topic "Twinkle Twinkle Little Star"

# Batch produce 5 nursery rhymes
python main.py produce --count 5 --niche nursery_rhymes

# See song ideas
python main.py topics --niche nursery_rhymes
```

### 5. Start the Dashboard

```bash
python main.py dashboard
# → Open http://localhost:5000
```

### 6. Enable Auto-Posting

```bash
# Posts 1 rhyme/day at the configured time automatically
python main.py schedule --niche nursery_rhymes
```

---

## Commands

| Command | Description |
|---------|-------------|
| `python main.py produce` | Produce & upload a nursery rhyme video |
| `python main.py produce --count 5` | Batch produce 5 songs |
| `python main.py produce --dry-run` | Lyrics + SEO only |
| `python main.py topics` | List song ideas |
| `python main.py thumbnail "Title Here"` | Generate thumbnail variants |
| `python main.py schedule` | Start auto-posting scheduler |
| `python main.py status` | Show video pipeline status |
| `python main.py dashboard` | Launch web dashboard |

---

## Configuration

Edit `config.yaml` to customize:
- **Channel name / tagline** (`channel.name`, `channel.tagline`)
- **Style** (`nursery_rhymes`, `lullabies`, `learning_songs`)
- **Made for Kids flag** (`channel.made_for_kids` — keep `true`)
- **Kid voice** (`tts.edge_voice`, e.g. `en-US-AnaNeural` child voice, or `en-US-JennyNeural`)
- **Bright visuals** (colors under `video:` and `thumbnail:`)
- **Upload schedule** (`videos_per_week`, `upload_time`)

---

## Project Structure

```
Youtube-Faceless/
├── main.py                 # CLI entry point
├── config.yaml             # Channel configuration (Twinkle Tots)
├── requirements.txt
├── src/
│   ├── pipeline.py         # Main orchestration
│   ├── script_generator.py # AI nursery rhyme lyrics
│   ├── voiceover.py        # edge-tts / ElevenLabs / OpenAI / gTTS
│   ├── video_creator.py    # Video assembly
│   ├── thumbnail.py        # Bright kid-friendly thumbnails
│   ├── seo.py              # Kid-safe titles/descriptions/tags
│   ├── uploader.py         # YouTube Data API v3 (Made for Kids ✓)
│   ├── scheduler.py        # Content calendar
│   ├── topics.py           # Song idea discovery
│   └── database.py         # SQLite data layer
├── dashboard/              # Flask dashboard
├── output/                 # Generated content (gitignored)
├── assets/
│   ├── fonts/              # Drop .ttf fonts here
│   └── music/              # Drop royalty-free kids .mp3 here
└── credentials/            # YouTube OAuth (gitignored)
```

---

## Adding Background Music

Drop royalty-free, kid-friendly MP3 files into `assets/music/` (gentle instrumental /
music-box tracks work great). One is picked at random per video. Good sources:
- [YouTube Audio Library](https://studio.youtube.com/channel/*/music) (filter to Children's / Happy)
- [Pixabay Music](https://pixabay.com/music/)

---

## Voice Options (edge-tts, free)

Set `tts.edge_voice` in `config.yaml`:
- `en-US-AnaNeural` – child-like, gentle (default)
- `en-US-JennyNeural` – warm, friendly female
- `en-GB-MaisieNeural` – British child voice
- `en-US-AriaNeural` – bright, expressive

For singing-quality vocals, use ElevenLabs (`ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`).

---

## Note on Quality

AI text-to-speech reads/chants the rhymes rather than singing them melodically. For a
polished channel, pair the generated lyrics + visuals with your own melody or a music
tool. The pipeline gets you a complete, uploadable video end-to-end automatically.
