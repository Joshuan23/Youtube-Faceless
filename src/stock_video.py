"""Pexels stock video downloader for b-roll footage."""

import os
import logging
import requests
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_API = "https://api.pexels.com/videos/search"

_NICHE_KEYWORDS = {
    "personal_finance": "money finance business",
    "ai_tech": "technology computer data",
    "business": "business office entrepreneur",
    "health": "fitness health wellness",
}


def _query(topic: str, niche: str = "") -> str:
    topic = re.sub(r"[?!,.\d]", "", topic.lower())
    stop = {"how", "to", "the", "a", "an", "for", "in", "on", "at", "of",
            "and", "or", "with", "your", "you", "ways", "steps", "best"}
    words = [w for w in topic.split() if w not in stop]
    q = " ".join(words[:3])
    return q or _NICHE_KEYWORDS.get(niche, "business success")


def get_clips(topic: str, niche: str = "", count: int = 4,
              output_dir: str = "/tmp/clips") -> list[str]:
    """Download stock clips from Pexels. Returns local file paths."""
    if not PEXELS_KEY:
        logger.info("No PEXELS_API_KEY — skipping stock footage")
        return []

    query = _query(topic, niche)
    logger.info("Pexels search: %s", query)

    try:
        resp = requests.get(
            PEXELS_API,
            headers={"Authorization": PEXELS_KEY},
            params={"query": query, "per_page": count + 3, "orientation": "landscape"},
            timeout=15,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
    except Exception as e:
        logger.warning("Pexels API error: %s", e)
        return []

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    paths = []

    for i, vid in enumerate(videos):
        if len(paths) >= count:
            break
        files = vid.get("video_files", [])
        # Prefer HD (1280w) for quality, avoid 4K for speed
        scored = sorted(
            [f for f in files if 854 <= f.get("width", 0) <= 1920],
            key=lambda f: abs(f.get("width", 0) - 1280),
        )
        chosen = scored[0] if scored else (files[0] if files else None)
        if not chosen or not chosen.get("link"):
            continue

        dest = str(Path(output_dir) / f"clip_{i}.mp4")
        try:
            r = requests.get(chosen["link"], timeout=60, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            paths.append(dest)
            logger.info("Clip %d downloaded (%dpx)", i, chosen.get("width", 0))
        except Exception as e:
            logger.warning("Clip %d download failed: %s", i, e)

    return paths
