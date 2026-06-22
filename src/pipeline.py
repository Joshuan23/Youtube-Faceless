"""Main orchestration pipeline: topic → script → voice → video → thumbnail → upload."""

import os
import logging
import re
from pathlib import Path
from datetime import datetime

import yaml

from .database import Database
from .topics import get_trending_topics
from .script_generator import ScriptGenerator
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

    def __init__(self, skip_upload: bool = False, dry_run: bool = False):
        self.config = _config()
        self.db = Database()
        self.skip_upload = skip_upload
        self.dry_run = dry_run  # if True, skip TTS/video (text-only mode)
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

    def run_topic(self, topic: str, niche: str = None) -> int:
        """Produce and upload a single video for a given topic. Returns video DB id."""
        niche = niche or self.config["channel"]["niche"]
        logger.info("▶ Pipeline start | niche=%s | topic=%s", niche, topic)

        video_id = self.db.create_video(topic, niche)

        try:
            video_id = self._step_script(video_id, topic, niche)
            if not self.dry_run:
                video_id = self._step_audio(video_id)
                video_id = self._step_video(video_id)
            video_id = self._step_thumbnail(video_id)
            if not self.skip_upload and not self.dry_run:
                video_id = self._step_upload(video_id)
        except Exception as e:
            self.db.update_video(video_id, status="error")
            logger.error("Pipeline failed for video %d: %s", video_id, e)
            raise

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
        logger.info("[1/5] Generating script…")
        self.db.update_video(video_id, status="scripting")
        script_data = self.script_gen.generate(topic, niche)
        seo_data = self.seo.generate(script_data)

        title = seo_data.get("recommended_title") or script_data.get("title") or topic
        description = self.seo.build_full_description(seo_data)
        tags = seo_data.get("tags", [])

        slug = _slugify(title)
        scripts_dir = OUTPUT_ROOT / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = str(scripts_dir / f"{slug}.txt")
        with open(script_path, "w") as f:
            f.write(script_data.get("full_script", ""))

        import json
        meta_path = str(scripts_dir / f"{slug}_meta.json")
        with open(meta_path, "w") as f:
            json.dump({**script_data, "seo": seo_data}, f, indent=2)

        self.db.update_video(
            video_id,
            status="scripted",
            title=title,
            description=description,
            tags=json.dumps(tags),
            script_path=script_path,
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
        video = self.db.get_video(video_id)
        audio_path = video["audio_path"]
        slug = _slugify(video["title"] or video["topic"])
        video_dir = OUTPUT_ROOT / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(video_dir / f"{slug}.mp4")

        import json as _json
        scripts_dir = OUTPUT_ROOT / "scripts"
        meta_path = scripts_dir / f"{slug}_meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                script_data = _json.load(f)
        else:
            script_data = {"title": video["title"], "sections": [], "niche": video["niche"]}

        creator = VideoCreator()
        creator.create(script_data, audio_path, output_path, broll_query=video["topic"])

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

    def _step_upload(self, video_id: int) -> int:
        logger.info("[5/5] Uploading to YouTube…")
        video = self.db.get_video(video_id)
        import json as _json
        tags = _json.loads(video["tags"]) if video["tags"] else []

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
        logger.info("Published: %s", result["youtube_url"])
        return video_id
