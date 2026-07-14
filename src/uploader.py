"""YouTube Data API v3 uploader with OAuth2 flow."""

import os
import logging
import json
import pickle
import time
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE = "youtube"
API_VERSION = "v3"
RESUMABLE_CHUNK = 1024 * 1024 * 50  # 50 MB

# Default fallback categories per kids-content style
CATEGORY_IDS = {
    "nursery_rhymes": "1",   # Film & Animation
    "lullabies": "10",       # Music
    "learning_songs": "27",  # Education
}


def _load_config() -> dict:
    try:
        p = Path(__file__).parent.parent / "config.yaml"
        with open(p) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _category_for(niche: str) -> str:
    """Prefer the per-niche category from config.yaml, else the built-in map."""
    cfg = _load_config()
    niche_cfg = (cfg.get("niches") or {}).get(niche) or {}
    return str(niche_cfg.get("youtube_category") or CATEGORY_IDS.get(niche, "1"))


def _made_for_kids() -> bool:
    """COPPA: children's content MUST be flagged as made for kids."""
    cfg = _load_config()
    return bool((cfg.get("channel") or {}).get("made_for_kids", True))


class YouTubeUploader:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request

        creds_path = Path(__file__).parent.parent / "credentials"
        token_path = creds_path / "token.pickle"

        creds = None

        # Try loading from env var first (survives redeployments)
        token_b64 = os.getenv("YOUTUBE_TOKEN_B64")
        if token_b64:
            import base64
            try:
                creds = pickle.loads(base64.b64decode(token_b64))
            except Exception:
                creds = None

        if not creds and token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds:
            raise RuntimeError(
                "YouTube not connected. Go to /youtube-auth in the dashboard to connect."
            )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Persist refreshed token
            creds_path.mkdir(parents=True, exist_ok=True)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        if not creds.valid:
            raise RuntimeError(
                "YouTube credentials invalid. Go to /youtube-auth to reconnect."
            )

        self._service = build(API_SERVICE, API_VERSION, credentials=creds)
        return self._service

    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: str = None,
        niche: str = "nursery_rhymes",
        privacy: str = "public",
    ) -> dict:
        """Upload video to YouTube. Returns dict with youtube_id and youtube_url."""
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        category_id = _category_for(niche)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:15],
                "categoryId": category_id,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": _made_for_kids(),
            },
        }

        media = MediaFileUpload(
            video_path,
            chunksize=RESUMABLE_CHUNK,
            resumable=True,
            mimetype="video/mp4",
        )

        logger.info("Uploading: %s", title)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.info("Upload progress: %d%%", pct)

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info("Uploaded: %s → %s", title, video_url)

        if thumbnail_path and Path(thumbnail_path).exists():
            self._set_thumbnail(service, video_id, thumbnail_path)

        return {"youtube_id": video_id, "youtube_url": video_url}

    def _set_thumbnail(self, service, video_id: str, thumbnail_path: str):
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        try:
            service.thumbnails().set(videoId=video_id, media_body=media).execute()
            logger.info("Thumbnail set for %s", video_id)
        except Exception as e:
            logger.warning("Thumbnail upload failed: %s", e)

    def schedule_video(
        self, video_path: str, title: str, description: str, tags: list[str],
        publish_at: str, thumbnail_path: str = None, niche: str = "nursery_rhymes",
    ) -> dict:
        """Upload as 'private', then schedule publish time (ISO 8601 UTC)."""
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        category_id = _category_for(niche)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:15],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at,
                "selfDeclaredMadeForKids": _made_for_kids(),
            },
        }
        media = MediaFileUpload(video_path, chunksize=RESUMABLE_CHUNK, resumable=True, mimetype="video/mp4")
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response["id"]
        if thumbnail_path and Path(thumbnail_path).exists():
            self._set_thumbnail(service, video_id, thumbnail_path)

        return {
            "youtube_id": video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "scheduled_at": publish_at,
        }
