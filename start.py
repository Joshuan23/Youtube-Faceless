#!/usr/bin/env python3
"""
STEP-BY-STEP starter script.
Run each step individually to understand the pipeline before automating.

Usage:
  python start.py step1   # Get topic ideas
  python start.py step2   # Write a script
  python start.py step3   # Generate voiceover
  python start.py step4   # Build the video
  python start.py step5   # Create thumbnail
  python start.py step6   # Upload to YouTube
  python start.py all     # Run all steps in order
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  CHANGE THESE to customize your channel
# ─────────────────────────────────────────────
NICHE  = "personal_finance"   # or: ai_tech | business | health
TOPIC  = ""                   # leave blank to auto-pick a trending topic
# ─────────────────────────────────────────────


def check_keys():
    from src.llm import active_provider
    provider = active_provider()
    if provider == "none":
        print("\n❌  No LLM API key found in .env")
        print()
        print("   FREE option (no credit card):")
        print("   1. Go to https://console.groq.com")
        print("   2. Sign up → Create API Key")
        print("   3. Add to .env:  GROQ_API_KEY=gsk_xxxx")
        print()
        print("   Also free: GEMINI_API_KEY from https://aistudio.google.com/apikey")
        sys.exit(1)
    print(f"  LLM provider: {provider}")


def step1_pick_topic():
    """Step 1 – Pick a trending topic for your niche."""
    print("\n━━━ STEP 1: Find a great topic ━━━")
    from src.topics import get_trending_topics

    topics = get_trending_topics(NICHE, count=10)
    print(f"\nTop 10 topic ideas for '{NICHE}':\n")
    for i, t in enumerate(topics, 1):
        print(f"  {i:2}. {t}")

    chosen = topics[0]
    print(f"\n✓ Using: \"{chosen}\"")
    print("  (Edit TOPIC at the top of start.py to use a different one)")
    _save_state("topic", chosen)
    return chosen


def step2_write_script(topic: str = None):
    """Step 2 – Write a full YouTube script with Claude."""
    print("\n━━━ STEP 2: Write the script ━━━")
    topic = topic or _load_state("topic")
    if not topic:
        print("❌ Run step1 first.")
        return

    print(f"  Topic: {topic}")
    print("  Calling Claude to write a 12-minute script…")

    from src.script_generator import ScriptGenerator
    gen = ScriptGenerator()
    script_data = gen.generate(topic, NICHE)

    title = script_data.get("title", topic)
    words = script_data.get("word_count", 0)
    duration = script_data.get("estimated_duration_min", 0)

    print(f"\n  Title:    {title}")
    print(f"  Words:    {words:,}")
    print(f"  Duration: ~{duration:.1f} min")
    print(f"  Sections: {len(script_data.get('sections', []))}")

    # Also generate SEO
    print("\n  Generating SEO metadata…")
    from src.seo import SEOOptimizer
    seo = SEOOptimizer().generate(script_data)
    script_data["seo"] = seo

    print(f"  Recommended title: {seo.get('recommended_title')}")
    print(f"  Tags: {', '.join((seo.get('tags') or [])[:5])} …")

    # Save everything
    import json, re
    slug = re.sub(r"[^\w-]", "-", title.lower())[:50]
    out_dir = Path("output/scripts")
    out_dir.mkdir(parents=True, exist_ok=True)

    script_path = out_dir / f"{slug}.txt"
    meta_path   = out_dir / f"{slug}_meta.json"
    script_path.write_text(script_data.get("full_script", ""))
    meta_path.write_text(json.dumps(script_data, indent=2))

    print(f"\n✓ Script saved → {script_path}")
    _save_state("script_path", str(script_path))
    _save_state("meta_path",   str(meta_path))
    _save_state("title",       seo.get("recommended_title") or title)
    return str(script_path)


def step3_make_voiceover(script_path: str = None):
    """Step 3 – Turn the script into a spoken voiceover (MP3)."""
    print("\n━━━ STEP 3: Generate voiceover ━━━")
    script_path = script_path or _load_state("script_path")
    if not script_path or not Path(script_path).exists():
        print("❌ Run step2 first.")
        return

    text = Path(script_path).read_text()
    print(f"  Script length: {len(text):,} characters")

    from src.voiceover import VoiceoverGenerator
    tts_provider = VoiceoverGenerator()._detect_provider()
    print(f"  TTS provider: {tts_provider}")
    if tts_provider == "gtts":
        print("\n  ⚠  Using gTTS (robotic quality).")
        print("     For free natural voice: pip install edge-tts")

    import re
    title = _load_state("title") or "video"
    slug = re.sub(r"[^\w-]", "-", title.lower())[:50]

    from src.voiceover import generate_chunked
    audio_path = generate_chunked(text, "output/audio", slug)

    size_mb = Path(audio_path).stat().st_size / 1_000_000
    print(f"\n✓ Audio saved → {audio_path}  ({size_mb:.1f} MB)")
    _save_state("audio_path", audio_path)
    return audio_path


def step4_make_video(audio_path: str = None):
    """Step 4 – Assemble the video (slides + voiceover + music)."""
    print("\n━━━ STEP 4: Build the video ━━━")
    audio_path = audio_path or _load_state("audio_path")
    meta_path  = _load_state("meta_path")

    if not audio_path or not Path(audio_path).exists():
        print("❌ Run step3 first.")
        return

    import json, re
    script_data = json.loads(Path(meta_path).read_text()) if meta_path else {}
    title = _load_state("title") or "video"
    slug  = re.sub(r"[^\w-]", "-", title.lower())[:50]

    out_dir = Path("output/videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(out_dir / f"{slug}.mp4")

    print("  Assembling slides + audio…  (this takes 1-3 min)")
    print("  ⚠  Requires ffmpeg installed on your system")

    from src.video_creator import VideoCreator
    VideoCreator().create(script_data, audio_path, video_path)

    size_mb = Path(video_path).stat().st_size / 1_000_000
    print(f"\n✓ Video saved → {video_path}  ({size_mb:.1f} MB)")
    _save_state("video_path", video_path)
    return video_path


def step5_make_thumbnail():
    """Step 5 – Generate 3 thumbnail variants."""
    print("\n━━━ STEP 5: Create thumbnails ━━━")
    title = _load_state("title") or "Video Title"
    topic = _load_state("topic") or title

    from src.thumbnail import ThumbnailCreator
    paths = ThumbnailCreator().create_ab_set(title, topic, "output/thumbnails")

    for p in paths:
        print(f"  ✓ {p}")

    print(f"\n✓ 3 thumbnail variants saved to output/thumbnails/")
    print("  Pick the best one before uploading.")
    _save_state("thumb_path", paths[0])
    return paths[0]


def step6_upload():
    """Step 6 – Upload to YouTube."""
    print("\n━━━ STEP 6: Upload to YouTube ━━━")

    video_path = _load_state("video_path")
    thumb_path = _load_state("thumb_path")
    meta_path  = _load_state("meta_path")

    if not video_path or not Path(video_path).exists():
        print("❌ Run step4 first (no video found).")
        return

    import json
    meta = json.loads(Path(meta_path).read_text()) if meta_path else {}
    seo  = meta.get("seo", {})

    title       = seo.get("recommended_title") or _load_state("title") or "Video"
    tags        = seo.get("tags", [])

    from src.seo import SEOOptimizer
    description = SEOOptimizer().build_full_description(seo)

    print(f"  Title: {title}")
    print(f"  Tags:  {len(tags)} tags")
    print()

    secrets = Path("credentials/client_secrets.json")
    if not secrets.exists():
        print("⚠  YouTube credentials not found.")
        print("   To set up YouTube upload:")
        print("   1. Go to https://console.cloud.google.com")
        print("   2. Create project → Enable 'YouTube Data API v3'")
        print("   3. Create OAuth 2.0 credentials → Download JSON")
        print("   4. Save as credentials/client_secrets.json")
        print()
        print("   Skipping upload for now. Your video is ready at:")
        print(f"   {video_path}")
        return

    from src.uploader import YouTubeUploader
    result = YouTubeUploader().upload(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        thumbnail_path=thumb_path,
        niche=NICHE,
    )
    print(f"\n🎉 Published: {result['youtube_url']}")
    return result


def run_all():
    """Run all 6 steps in sequence."""
    check_keys()
    topic      = TOPIC or step1_pick_topic()
    script     = step2_write_script(topic)
    audio      = step3_make_voiceover(script)
    video      = step4_make_video(audio)
    thumb      = step5_make_thumbnail()
    step6_upload()


# ── State helpers (persist between steps) ──────────────────────────────────

STATE_FILE = Path("output/.state.json")

def _save_state(key: str, value: str):
    import json
    STATE_FILE.parent.mkdir(exist_ok=True)
    data = {}
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    data[key] = value
    STATE_FILE.write_text(json.dumps(data, indent=2))

def _load_state(key: str) -> str | None:
    import json
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text()).get(key)
    except Exception:
        return None


# ── Entry point ─────────────────────────────────────────────────────────────

STEPS = {
    "step1": step1_pick_topic,
    "step2": step2_write_script,
    "step3": step3_make_voiceover,
    "step4": step4_make_video,
    "step5": step5_make_thumbnail,
    "step6": step6_upload,
    "all":   run_all,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in STEPS:
        print(__doc__)
        print("Steps:")
        for name, fn in STEPS.items():
            print(f"  {name:8} – {fn.__doc__.strip()}")
        sys.exit(0)

    check_keys()
    STEPS[sys.argv[1]]()
