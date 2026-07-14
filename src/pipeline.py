"""Main orchestration pipeline: topic → script → voice → thumbnail → video → upload."""

import os
import logging
import re
from pathlib import Path
from datetime import datetime

import yaml

from .database import Database
from .topics import get_trending_topics
from .script_generator import ScriptGenerator, SECTION_TEMPLATES
from .voiceover import generate_chunked
from .thumbnail import ThumbnailCreator
from .seo import SEOOptimizer
from .uploader import YouTubeUploader

logger = logging.getLogger(__name__)

OUTPUT_ROOT = Path(__file__).parent.parent / "output"


def _config():
    p = Path(__file__).parent.parent / "config.yaml"
    with open(p) as f:
        return yaml.safe_load(f)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60]


class Pipeline:
    """End-to-end YouTube video production pipeline."""

    def __init__(self, skip_upload: bool = False, dry_run: bool = False, speed_mode: bool = False):
        self.config = _config()
        self.db = Database()
        self.skip_upload = skip_upload
        self.dry_run = dry_run
        self.speed_mode = speed_mode
        self.progress: dict = {}  # {video_id: {"step": str, "pct": int}}

    def _progress(self, video_id: int, step: str, pct: int):
        self.progress[video_id] = {"step": step, "pct": pct}
        logger.info("[%3d%%] %s", pct, step)

    def run_topic(self, topic: str, niche: str = None, video_id: int = None) -> int:
        """Produce and upload a single video. Returns video DB id."""
        niche = niche or self.config["channel"]["niche"]
        video_id = video_id or self.db.create_video(topic, niche)

        # Clear stale error from any previous attempt
        self.db.update_video(video_id, last_error=None)
        self._progress(video_id, "Starting…", 0)
        logger.info("▶ START video=%d niche=%s speed=%s topic=%s", video_id, niche, self.speed_mode, topic)

        try:
            self._progress(video_id, "Writing script…", 10)
            self._step_script(video_id, topic, niche)

            if not self.dry_run:
                self._progress(video_id, "Generating voiceover…", 30)
                self._step_audio(video_id)

                self._progress(video_id, "Creating thumbnail…", 55)
                self._step_thumbnail(video_id)

                self._progress(video_id, "Assembling video…", 65)
                self._step_video(video_id)

                if not self.skip_upload:
                    self._progress(video_id, "Uploading to YouTube…", 85)
                    self._step_upload(video_id)
            else:
                self._progress(video_id, "Creating thumbnail…", 70)
                self._step_thumbnail(video_id)

        except Exception as e:
            err = str(e)
            self.db.update_video(video_id, status="error", last_error=err)
            self._progress(video_id, f"Error: {err}", -1)
            logger.error("✗ FAILED video=%d: %s", video_id, err, exc_info=True)
            raise

        self._progress(video_id, "Done!", 100)
        logger.info("✓ DONE video=%d", video_id)
        return video_id

    def run_batch(self, count: int = 1, niche: str = None) -> list[int]:
        niche = niche or self.config["channel"]["niche"]
        topics = get_trending_topics(niche, count=count)
        ids = []
        for topic in topics[:count]:
            try:
                ids.append(self.run_topic(topic, niche))
            except Exception as e:
                logger.error("Batch item failed: %s | %s", topic, e)
        return ids

    # ── Steps ──────────────────────────────────────────────────────────────

    def _step_script(self, video_id: int, topic: str, niche: str):
        import json
        self.db.update_video(video_id, status="scripting")

        script_gen = ScriptGenerator()
        seo_opt = SEOOptimizer()

        if self.speed_mode:
            script_data = script_gen.generate_speed(topic, niche)
            seo_data    = seo_opt.generate_speed(script_data)
        else:
            meta = script_gen.generate_meta(topic, niche)
            section_names = SECTION_TEMPLATES.get(niche, SECTION_TEMPLATES["nursery_rhymes"])
            seo_input = {
                "topic": topic, "niche": niche,
                "title": meta.get("title", topic),
                "key_takeaways": meta.get("key_takeaways", []),
                "sections": [{"name": s} for s in section_names],
            }
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as ex:
                sf = ex.submit(script_gen.generate_script_text, topic, niche)
                ef = ex.submit(seo_opt.generate, seo_input)
                full_script_text = sf.result()
                seo_data = ef.result()
            script_data = script_gen.build_result(meta, full_script_text, topic, niche)

        title       = seo_data.get("recommended_title") or script_data.get("title") or topic
        description = seo_opt.build_full_description(seo_data)
        tags        = seo_data.get("tags", [])
        full_script = script_data.get("full_script", "").strip()

        if not full_script:
            raise RuntimeError("LLM returned an empty script — retry to regenerate.")

        slug = _slugify(title)
        scripts_dir = OUTPUT_ROOT / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = str(scripts_dir / f"{slug}.txt")
        with open(script_path, "w") as f:
            f.write(full_script)

        meta_path = str(scripts_dir / f"{slug}_meta.json")
        with open(meta_path, "w") as f:
            json.dump({**script_data, "seo": seo_data}, f, indent=2)

        self.db.update_video(
            video_id, status="scripted",
            title=title, description=description,
            tags=json.dumps(tags), script_path=script_path,
        )
        logger.info("[1/5] Script: %s (%d words)", script_path, len(full_script.split()))

    def _step_audio(self, video_id: int):
        video = self.db.get_video(video_id)
        script_path = video.get("script_path") or ""

        if not script_path or not Path(script_path).exists():
            raise RuntimeError(f"Script file missing — retry from scratch. (path: {script_path})")

        text = Path(script_path).read_text().strip()
        if not text:
            raise RuntimeError("Script file is empty — retry to regenerate.")

        slug = _slugify(video.get("title") or video.get("topic") or "video")
        audio_dir = OUTPUT_ROOT / "audio"
        audio_path = generate_chunked(text, str(audio_dir), slug)

        if not Path(audio_path).exists():
            raise RuntimeError(f"Audio was not created — edge-tts may have failed. Path: {audio_path}")

        self.db.update_video(video_id, audio_path=audio_path, status="voiced")
        logger.info("[2/5] Audio: %s", audio_path)

    def _step_thumbnail(self, video_id: int):
        video = self.db.get_video(video_id)
        title = video.get("title") or video.get("topic") or "Twinkle Tots"
        topic = video.get("topic") or title
        slug  = _slugify(title)
        thumb_dir = OUTPUT_ROOT / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = str(thumb_dir / f"{slug}_thumb.jpg")

        ThumbnailCreator().create(title, topic, thumb_path, variant=video_id % 5)

        if not Path(thumb_path).exists():
            raise RuntimeError(f"Thumbnail was not created. Path: {thumb_path}")

        self.db.update_video(video_id, thumb_path=thumb_path, status="thumbnailed")
        logger.info("[3/5] Thumbnail: %s", thumb_path)

    def _step_video(self, video_id: int):
        video = self.db.get_video(video_id)
        audio_path = video.get("audio_path") or ""
        thumb_path = video.get("thumb_path") or ""
        title = video.get("title") or video.get("topic") or "Twinkle Tots"
        niche = video.get("niche") or "nursery_rhymes"
        topic = video.get("topic") or title

        if not audio_path or not Path(audio_path).exists():
            raise RuntimeError(f"Audio file missing before video assembly: {audio_path}")

        slug = _slugify(title)
        video_dir = OUTPUT_ROOT / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(video_dir / f"{slug}.mp4")

        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            import shutil
            ffmpeg = shutil.which("ffmpeg") or "ffmpeg"

        from .stock_video import get_clips
        clips = get_clips(topic, niche, count=4, output_dir=str(OUTPUT_ROOT / "clips" / slug))

        if clips:
            output_path = self._make_footage_video(ffmpeg, clips, audio_path, title, output_path)
        else:
            output_path = self._make_static_video(ffmpeg, thumb_path, audio_path, output_path)

        if not Path(output_path).exists():
            raise RuntimeError(f"Video file not found after ffmpeg: {output_path}")

        size_mb = Path(output_path).stat().st_size / 1_000_000
        self.db.update_video(video_id, video_path=output_path, status="produced")
        logger.info("[4/5] Video: %s (%.1f MB)", output_path, size_mb)

    def _make_footage_video(self, ffmpeg: str, clips: list, audio_path: str,
                            title: str, output_path: str) -> str:
        import subprocess
        concat_path = output_path.replace(".mp4", "_concat.txt")
        with open(concat_path, "w") as f:
            for _ in range(8):
                for clip in clips:
                    f.write(f"file '{clip}'\n")

        safe_title = title.replace("'", "").replace(":", " -").replace("\\", "")[:55]
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        ]
        font_path = next((f for f in font_candidates if Path(f).exists()), None)

        if font_path:
            vf = (
                "scale=1280:720:force_original_aspect_ratio=increase,"
                "crop=1280:720,"
                "drawbox=x=0:y=h-80:w=iw:h=80:color=black@0.8:t=fill,"
                f"drawtext=fontfile='{font_path}':"
                f"text='{safe_title}':"
                "fontsize=28:fontcolor=white:x=(w-text_w)/2:y=h-57"
            )
        else:
            vf = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"

        cmd = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", concat_path,
            "-i", audio_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-threads", "0", "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        try:
            Path(concat_path).unlink()
        except Exception:
            pass

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-300:]
            logger.warning("Footage video failed (%s) — falling back to static", err[-80:])
            return self._make_static_video(ffmpeg, "", audio_path, output_path)

        return output_path

    def _make_static_video(self, ffmpeg: str, thumb_path: str,
                           audio_path: str, output_path: str) -> str:
        import subprocess
        if thumb_path and Path(thumb_path).exists():
            img_args = ["-loop", "1", "-r", "1", "-i", thumb_path]
        else:
            img_args = ["-f", "lavfi", "-i", "color=c=#7EC8F3:s=1280x720:r=1"]

        cmd = (
            [ffmpeg, "-y"] + img_args +
            ["-i", audio_path,
             "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
             "-c:a", "aac", "-b:a", "128k",
             "-pix_fmt", "yuv420p", "-shortest", output_path]
        )
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-600:]
            raise RuntimeError(f"ffmpeg static video failed (rc={result.returncode}): {err[-200:]}")
        return output_path

    def _do_upload(self, video_id: int):
        import json as _json
        video = self.db.get_video(video_id)
        if not video:
            raise RuntimeError(f"Video {video_id} not found in DB")

        video_path = video.get("video_path") or ""
        if not video_path or not Path(video_path).exists():
            raise RuntimeError(
                "Video file is missing (server restarted, files cleared). Click ↺ Run to rebuild."
            )

        try:
            tags = _json.loads(video["tags"]) if video.get("tags") else []
        except Exception:
            tags = []

        result = YouTubeUploader().upload(
            video_path=video_path,
            title=(video.get("title") or video.get("topic") or "Video")[:100],
            description=(video.get("description") or video.get("topic") or "")[:5000],
            tags=tags,
            thumbnail_path=video.get("thumb_path") or "",
            niche=video.get("niche") or "nursery_rhymes",
        )
        self.db.update_video(
            video_id,
            youtube_id=result["youtube_id"],
            youtube_url=result["youtube_url"],
            uploaded_at=datetime.utcnow().isoformat(),
            status="uploaded",
            last_error=None,
        )
        self._progress(video_id, "Uploaded to YouTube!", 100)
        logger.info("[5/5] Published: %s", result["youtube_url"])

    def _step_upload(self, video_id: int):
        self.db.update_video(video_id, status="uploading")
        try:
            self._do_upload(video_id)
        except Exception as e:
            err = str(e)
            self.db.update_video(video_id, status="error", last_error=err)
            self._progress(video_id, f"Upload failed: {err}", -1)
            logger.error("[5/5] Upload FAILED video=%d: %s", video_id, err)
            raise
