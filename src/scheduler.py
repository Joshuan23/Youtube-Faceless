"""Content calendar & upload scheduler."""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _config():
    p = Path(__file__).parent.parent / "config.yaml"
    with open(p) as f:
        return yaml.safe_load(f)


SCHEDULE_DAYS = {
    "daily": list(range(7)),
    "5x_week": [0, 1, 2, 3, 4],        # Mon–Fri
    "3x_week": [0, 2, 4],               # Mon, Wed, Fri
    "2x_week": [1, 4],                  # Tue, Fri
}


def next_upload_times(count: int = 7) -> list[datetime]:
    """Return the next `count` scheduled upload datetimes."""
    cfg = _config()
    upload_time_str = cfg["channel"].get("upload_time", "15:00")
    schedule_key = cfg["channel"].get("upload_schedule", "5x_week")
    days = SCHEDULE_DAYS.get(schedule_key, SCHEDULE_DAYS["5x_week"])

    hour, minute = map(int, upload_time_str.split(":"))
    now = datetime.utcnow()
    result = []
    cursor = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    while len(result) < count:
        if cursor <= now:
            cursor += timedelta(hours=1)
            continue
        if cursor.weekday() in days:
            result.append(cursor)
        cursor += timedelta(days=1)
        cursor = cursor.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return result


def run_daily_pipeline(pipeline_fn, niche: str = None):
    """
    Blocking scheduler: calls pipeline_fn(niche) every day at configured time.
    pipeline_fn should accept niche: str and return a video_id.
    """
    cfg = _config()
    upload_time_str = cfg["channel"].get("upload_time", "15:00")
    niche = niche or cfg["channel"].get("niche", "personal_finance")
    schedule_key = cfg["channel"].get("upload_schedule", "5x_week")
    days = SCHEDULE_DAYS.get(schedule_key, SCHEDULE_DAYS["5x_week"])
    hour, minute = map(int, upload_time_str.split(":"))

    logger.info("Scheduler started. Niche=%s, Schedule=%s, Time=%s", niche, schedule_key, upload_time_str)
    print(f"[Scheduler] Running on {schedule_key} schedule at {upload_time_str} UTC")
    print("[Scheduler] Press Ctrl+C to stop.")

    try:
        while True:
            now = datetime.utcnow()
            if now.weekday() in days and now.hour == hour and now.minute == minute:
                logger.info("Scheduled trigger: running pipeline")
                try:
                    pipeline_fn(niche)
                except Exception as e:
                    logger.error("Pipeline error: %s", e)
                time.sleep(61)  # avoid double-trigger within the same minute
            else:
                time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
