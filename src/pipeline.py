"""Main orchestration pipeline: topic → script → voice → video → thumbnail → upload."""

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
from .video_creator import VideoCreator
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
        self.speed_mode = speed_mode  # 4-min video, fast model, background upload
        self.progress: dict = {}      # {video_id: {"step": str, "pct": int}}
        self._script_gen = None
        self._seo = None
        self._voice_gen = None
        self._video_creator = None
        self._thumbnail = None
        self._uploader = None

    # ── Lazy-loaded components ──────────────────────────────────────────────

    @property
    def script_gen(self):
        if not self._script_gen:
            self._script_gen = ScriptGenerator()
        return self._script_gen

    @property
    def seo(self):
        if not self._seo:
            self._seo = SEOOptimizer()
        return self._seo

    @property
    def thumbnail(self):
        if not self._thumbnail:
            self._thumbnail = ThumbnailCreator()
        return self._thumbnail

    @property
    def uploader(self):
        if not self._uploader:
            self._uploader = YouTubeUploader()
        return self._uploader

    # ── Main entrypoints ────────────────────────────────────────────────────

    def _progress(self, video_id: int, step: str, pct: int):
        self.progress[video_id] = {"step": step, "pct": pct}

    def run_topic(self, topic: str, niche: str = None, video_id: int = None) -> int:
        """Produce and upload a single video for a given topic. Returns video DB id."""
        niche = niche or self.config["channel"]["niche"]
        logger.info("▶ Pipeline start | niche=%s | topic=%s | speed=%s", niche, topic, self.speed_mode)

        video_id = video_id or self.db.create_video(topic, niche)
        self._progress(video_id, "Starting…", 0)

        try:
            self._progress(video_id, "Writing script…", 5)
            video_id = self._step_script(video_id, topic, niche)
            if not self.dry_run:
                self._progress(video_id, "Generating voiceover…", 35)
                video_id = self._step_audio(video_id)
                self._progress(video_id, "Creating thumbnail…", 60)
                video_id = self._step_thumbnail(video_id)
                self._progress(video_id, "Assembling video…", 70)
                video_id = self._step_video(video_id)
            else:
                self._progress(video_id, "Creating thumbnail…", 60)
                video_id = self._step_thumbnail(video_id)
            if not self.skip_upload and not self.dry_run:
                self._progress(video_id, "Uploading to YouTube…", 85)
                video_id = self._step_upload(video_id)
        except Exception as e:
            self.db.update_video(video_id, status="error")
            self._progress(video_id, f"Error: {e}", -1)
            logger.error("Pipeline failed for video %d: %s", video_id, e)
            raise

        self._progress(video_id, "Done!", 100)
        logger.info("✓ Pipeline complete | video_id=%d", video_id)
        return video_id

    def run_batch(self, count: int = 1, niche: str = None) -> list[int]:
        """Produce `count` videos using trending topics."""
        niche = niche or self.config["channel"]["niche"]
        topics = get_trending_topics(niche, count=count)
        ids = []
        for topic in topics[:count]:
            try:
                vid_id = self.run_topic(topic, niche)
                ids.append(vid_id)
            except Exception as e:
                logger.error("Batch item failed: %s | %s", topic, e)
        return ids

    # ── Steps ───────────────────────────────────────────────────────────────

    def _step_script(self, video_id: int, topic: str, niche: str) -> int:
        import json
        from concurrent.futures import ThreadPoolExecutor

        logger.info("[1/5] Generating script… (speed=%s)", self.speed_mode)
        self.db.update_video(video_id, status="scripting")

        if self.speed_mode:
            # Single fast call (~5s) + instant SEO (0s)
            script_data = self.script_gen.generate_speed(topic, niche)
            seo_data    = self.seo.generate_speed(script_data)
        else:
            # Phase 1 — meta only (~3s)
            meta = self.script_gen.generate_meta(topic, niche)
            # Phase 2 — full script + SEO in parallel (~20s)
            section_names = SECTION_TEMPLATES.get(niche, SECTION_TEMPLATES["personal_finance"])
            seo_input = {
                "topic": topic, "niche": niche,
                "title": meta.get("title", topic),
                "key_takeaways": meta.get("key_takeaways", []),
                "sections": [{"name": s} for s in section_names],
            }
            with ThreadPoolExecutor(max_workers=2) as ex:
                script_future = ex.submit(self.script_gen.generate_script_text, topic, niche)
                seo_future    = ex.submit(self.seo.generate, seo_input)
                full_script   = script_future.result()
                seo_data      = seo_future.result()
            script_data = self.script_gen.build_result(meta, full_script, topic, niche)

        title       = seo_data.get("recommended_title") or script_data.get("title") or topic
        description = self.seo.build_full_description(seo_data)
        tags        = seo_data.get("tags", [])

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
        logger.info("Script saved: %s", script_path)
        return video_id

    def _step_audio(self, video_id: int) -> int:
        logger.info("[2/5] Generating voiceover…")
        video = self.db.get_video(video_id)
        script_path = video["script_path"]
        with open(script_path) as f:
            text = f.read()

        slug = _slugify(video["title"] or video["topic"])
        audio_dir = OUTPUT_ROOT / "audio"
        audio_path = generate_chunked(text, str(audio_dir), slug)

        self.db.update_video(video_id, audio_path=audio_path, status="voiced")
        return video_id

    def _step_video(self, video_id: int) -> int:
        logger.info("[3/5] Assembling video…")
        import subprocess
        video = self.db.get_video(video_id)
        audio_path = video["audio_path"]
        thumb_path = video.get("thumb_path") or ""
        slug = _slugify(video["title"] or video["topic"])
        video_dir = OUTPUT_ROOT / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(video_dir / f"{slug}.mp4")

        if not audio_path or not Path(audio_path).exists():
            raise RuntimeError(f"Audio file missing: {audio_path}")

        # imageio-ffmpeg ships its own binary via pip — always available
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            import shutil
            ffmpeg = shutil.which("ffmpeg") or "ffmpeg"

        if thumb_path and Path(thumb_path).exists():
            img_args = ["-loop", "1", "-r", "1", "-i", thumb_path]
        else:
            img_args = ["-f", "lavfi", "-i", "color=c=#0d1117:s=1920x1080:r=1"]

        cmd = (
            [ffmpeg, "-y"] + img_args
            + ["-i", audio_path,
               "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
               "-c:a", "copy",
               "-pix_fmt", "yuv420p", "-shortest",
               output_path]
        )
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-600:]
            raise RuntimeError(f"ffmpeg rc={result.returncode}: {err}")

        self.db.update_video(video_id, video_path=output_path, status="produced")
        return video_id

    def _step_thumbnail(self, video_id: int) -> int:
        logger.info("[4/5] Creating thumbnail…")
        video = self.db.get_video(video_id)
        title = video["title"] or video["topic"]
        slug = _slugify(title)
        thumb_dir = OUTPUT_ROOT / "thumbnails"
        thumb_path = str(thumb_dir / f"{slug}_thumb_v1.jpg")

        self.thumbnail.create(title, video["topic"], thumb_path, variant=video_id % 5)
        self.db.update_video(video_id, thumb_path=thumb_path, status="thumbnailed")
        return video_id

    def _do_upload(self, video_id: int):
        import json as _json
        video = self.db.get_video(video_id)
        tags  = _json.loads(video["tags"]) if video["tags"] else []
        result = self.uploader.upload(
            video_path=video["video_path"],
            title=video["title"],
            description=video["description"],
            tags=tags,
            thumbnail_path=video["thumb_path"],
            niche=video["niche"],
        )
        self.db.update_video(
            video_id,
            youtube_id=result["youtube_id"],
            youtube_url=result["youtube_url"],
            uploaded_at=datetime.utcnow().isoformat(),
            status="uploaded",
        )
        self._progress(video_id, "Uploaded!", 100)
        logger.info("Published: %s", result["youtube_url"])

    def _step_upload(self, video_id: int) -> int:
        if self.speed_mode:
            # Fire-and-forget — pipeline returns immediately, upload continues in background
            import threading
            self.db.update_video(video_id, status="uploading")
            threading.Thread(target=self._do_upload, args=(video_id,), daemon=True).start()
            logger.info("[5/5] Upload started in background")
        else:
            logger.info("[5/5] Uploading to YouTube…")
            self._do_upload(video_id)
        return video_id
