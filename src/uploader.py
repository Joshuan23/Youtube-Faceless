"""YouTube Data API v3 uploader with OAuth2 flow."""

import os
import logging
import json
import pickle
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE = "youtube"
API_VERSION = "v3"
RESUMABLE_CHUNK = 1024 * 1024 * 10  # 10 MB

CATEGORY_IDS = {
    "personal_finance": "27",  # Education
    "ai_tech": "28",           # Science & Technology
    "business": "27",
    "health": "26",            # Howto & Style
}


class YouTubeUploader:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        creds_path = Path(__file__).parent.parent / "credentials"
        token_path = creds_path / "token.pickle"
        secrets_file = os.getenv(
            "YOUTUBE_CLIENT_SECRETS_FILE",
            str(creds_path / "client_secrets.json"),
        )

        creds = None
        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(secrets_file).exists():
                    raise FileNotFoundError(
                        f"YouTube client secrets not found: {secrets_file}\n"
                        "See README: https://developers.google.com/youtube/v3/getting-started"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
                creds = flow.run_console()
            creds_path.mkdir(parents=True, exist_ok=True)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        self._service = build(API_SERVICE, API_VERSION, credentials=creds)
        return self._service

    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: str = None,
        niche: str = "personal_finance",
        privacy: str = "public",
    ) -> dict:
        """Upload video to YouTube. Returns dict with youtube_id and youtube_url."""
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        category_id = CATEGORY_IDS.get(niche, "27")

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
                "selfDeclaredMadeForKids": False,
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
        publish_at: str, thumbnail_path: str = None, niche: str = "personal_finance",
    ) -> dict:
        """Upload as 'private', then schedule publish time (ISO 8601 UTC)."""
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        category_id = CATEGORY_IDS.get(niche, "27")

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
                "selfDeclaredMadeForKids": False,
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
