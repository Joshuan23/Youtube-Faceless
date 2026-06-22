"""Video assembly: combines voiceover, b-roll, text overlays, and background music."""

import os
import logging
import random
import textwrap
from pathlib import Path

import requests
import yaml

logger = logging.getLogger(__name__)

_CONFIG = None


def _config():
    global _CONFIG
    if _CONFIG is None:
        p = Path(__file__).parent.parent / "config.yaml"
        with open(p) as f:
            _CONFIG = yaml.safe_load(f)
    return _CONFIG


# ── Pexels B-roll ─────────────────────────────────────────────────────────────


def fetch_broll_clips(query: str, count: int = 5) -> list[str]:
    """Download stock video clips from Pexels. Returns list of local .mp4 paths."""
    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        logger.warning("PEXELS_API_KEY not set – skipping b-roll download")
        return []

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": count, "size": "medium"}
    resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=20)
    if resp.status_code != 200:
        logger.warning("Pexels API error %s", resp.status_code)
        return []

    clips_dir = Path(__file__).parent.parent / "output" / "broll"
    clips_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, video in enumerate(resp.json().get("videos", [])[:count]):
        # pick the SD file
        files = sorted(video.get("video_files", []), key=lambda x: x.get("width", 0))
        video_file = next((f for f in files if f.get("width", 0) <= 1280), files[0] if files else None)
        if not video_file:
            continue
        url = video_file["link"]
        dest = clips_dir / f"{query.replace(' ', '_')}_{i}.mp4"
        if not dest.exists():
            r = requests.get(url, stream=True, timeout=60)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        paths.append(str(dest))

    return paths


# ── Text Slide Fallback ───────────────────────────────────────────────────────


def make_text_slide(text: str, duration: float, width: int = 1920, height: int = 1080) -> object:
    """Create a MoviePy clip with text on dark background (no stock footage needed)."""
    from moviepy.editor import ColorClip, TextClip, CompositeVideoClip

    cfg = _config()["video"]
    bg = ColorClip(size=(width, height), color=_hex_to_rgb(cfg["background_color"]), duration=duration)

    lines = textwrap.wrap(text, width=40)
    display = "\n".join(lines[:4])  # max 4 lines

    try:
        txt = (
            TextClip(
                display,
                fontsize=cfg["font_size_body"],
                color=cfg["text_color"],
                font="DejaVu-Sans-Bold",
                method="caption",
                size=(width - 200, None),
                align="center",
            )
            .set_position("center")
            .set_duration(duration)
        )
    except Exception:
        # fallback if font not found
        txt = (
            TextClip(
                display,
                fontsize=cfg["font_size_body"],
                color=cfg["text_color"],
                method="label",
            )
            .set_position("center")
            .set_duration(duration)
        )

    return CompositeVideoClip([bg, txt])


def make_title_slide(title: str, subtitle: str = "", duration: float = 3.0) -> object:
    from moviepy.editor import ColorClip, TextClip, CompositeVideoClip

    cfg = _config()["video"]
    w, h = 1920, 1080
    bg = ColorClip(size=(w, h), color=_hex_to_rgb(cfg["background_color"]), duration=duration)
    clips = [bg]

    try:
        title_clip = (
            TextClip(
                title,
                fontsize=cfg["font_size_title"],
                color=cfg["accent_color"],
                font="DejaVu-Sans-Bold",
                method="caption",
                size=(w - 200, None),
                align="center",
            )
            .set_position(("center", h // 2 - 80))
            .set_duration(duration)
        )
        clips.append(title_clip)
        if subtitle:
            sub_clip = (
                TextClip(
                    subtitle,
                    fontsize=36,
                    color=cfg["text_color"],
                    font="DejaVu-Sans",
                    method="label",
                )
                .set_position(("center", h // 2 + 60))
                .set_duration(duration)
            )
            clips.append(sub_clip)
    except Exception as e:
        logger.warning("TextClip error: %s", e)

    return CompositeVideoClip(clips)


# ── Main Video Creator ────────────────────────────────────────────────────────


class VideoCreator:
    def __init__(self):
        self.config = _config()

    def create(
        self,
        script_data: dict,
        audio_path: str,
        output_path: str,
        broll_query: str = None,
    ) -> str:
        """
        Assemble the final video:
          1. Title slide (3s)
          2. Section slides synced to audio
          3. Optional b-roll overlay
          4. Background music mixed at low volume
        Returns output_path.
        """
        try:
            from moviepy.editor import (
                AudioFileClip,
                concatenate_videoclips,
                CompositeAudioClip,
                AudioClip,
            )
        except ImportError:
            raise ImportError("moviepy is required: pip install moviepy imageio[ffmpeg]")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        title = script_data.get("title", "Video")
        sections = script_data.get("sections", [])
        niche = script_data.get("niche", "")

        # Load voiceover
        voice = AudioFileClip(audio_path)
        total_duration = voice.duration

        # Distribute duration across slides
        slide_clips = [make_title_slide(title, niche.replace("_", " ").title(), 3.0)]
        section_duration = (total_duration - 3.0) / max(len(sections), 1)

        for section in sections:
            name = section.get("name", "")
            content = section.get("content", "")
            # Show section header for 2s, then content
            header_clip = make_title_slide(name, "", duration=2.0)
            body_preview = content[:200] + ("..." if len(content) > 200 else "")
            body_clip = make_text_slide(body_preview, max(section_duration - 2.0, 4.0))
            slide_clips.extend([header_clip, body_clip])

        video = concatenate_videoclips(slide_clips, method="compose")
        # Trim/extend to match audio
        if video.duration < total_duration:
            last = slide_clips[-1].set_duration(
                slide_clips[-1].duration + (total_duration - video.duration)
            )
            slide_clips[-1] = last
            video = concatenate_videoclips(slide_clips, method="compose")
        video = video.subclip(0, total_duration)

        # Mix background music
        bg_music_path = self._get_background_music()
        if bg_music_path:
            from moviepy.editor import AudioFileClip as AFC, CompositeAudioClip as CAC
            bg = AFC(bg_music_path).volumex(self.config["video"]["background_music_volume"])
            if bg.duration < total_duration:
                loops = int(total_duration / bg.duration) + 1
                from moviepy.editor import concatenate_audioclips
                bg = concatenate_audioclips([bg] * loops).subclip(0, total_duration)
            else:
                bg = bg.subclip(0, total_duration)
            final_audio = CompositeAudioClip([voice, bg])
        else:
            final_audio = voice

        video = video.set_audio(final_audio)

        cfg_video = self.config["video"]
        video.write_videofile(
            output_path,
            fps=cfg_video["fps"],
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,
        )
        logger.info("Video created: %s (%.1f min)", output_path, total_duration / 60)
        return output_path

    def _get_background_music(self) -> str | None:
        music_dir = Path(__file__).parent.parent / "assets" / "music"
        if music_dir.exists():
            mp3s = list(music_dir.glob("*.mp3"))
            if mp3s:
                return str(random.choice(mp3s))
        return None


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
