import sqlite3
import json
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "output" / "channel.db"


class Database:
    def __init__(self, path: str = None):
        self.path = path or str(DB_PATH)
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic       TEXT NOT NULL,
                    niche       TEXT NOT NULL,
                    title       TEXT,
                    description TEXT,
                    tags        TEXT,
                    script_path TEXT,
                    audio_path  TEXT,
                    video_path  TEXT,
                    thumb_path  TEXT,
                    youtube_id  TEXT,
                    youtube_url TEXT,
                    status      TEXT DEFAULT 'pending',
                    last_error  TEXT,
                    views       INTEGER DEFAULT 0,
                    revenue_usd REAL DEFAULT 0.0,
                    created_at  TEXT DEFAULT (datetime('now')),
                    uploaded_at TEXT,
                    updated_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS analytics (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id    INTEGER REFERENCES videos(id),
                    date        TEXT,
                    views       INTEGER DEFAULT 0,
                    watch_time_hrs REAL DEFAULT 0.0,
                    revenue_usd REAL DEFAULT 0.0,
                    cpm         REAL DEFAULT 0.0,
                    ctr         REAL DEFAULT 0.0,
                    avg_view_pct REAL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            # Migration: add last_error column if missing (existing databases)
            try:
                conn.execute("ALTER TABLE videos ADD COLUMN last_error TEXT")
            except Exception:
                pass  # column already exists

    # ── Videos ──────────────────────────────────────────────────────────────

    def create_video(self, topic: str, niche: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO videos (topic, niche) VALUES (?, ?)", (topic, niche)
            )
            return cur.lastrowid

    def update_video(self, video_id: int, **fields):
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE videos SET {set_clause} WHERE id = ?",
                list(fields.values()) + [video_id],
            )

    def get_video(self, video_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
            return dict(row) if row else None

    def list_videos(self, status: str = None, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM videos WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM videos ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Analytics ─────────────────────────────────────────────────────────

    def record_analytics(self, video_id: int, date: str, **metrics):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO analytics (video_id, date, views, watch_time_hrs,
                   revenue_usd, cpm, ctr, avg_view_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    video_id,
                    date,
                    metrics.get("views", 0),
                    metrics.get("watch_time_hrs", 0.0),
                    metrics.get("revenue_usd", 0.0),
                    metrics.get("cpm", 0.0),
                    metrics.get("ctr", 0.0),
                    metrics.get("avg_view_pct", 0.0),
                ),
            )

    def total_revenue(self) -> float:
        with self._conn() as conn:
            row = conn.execute("SELECT SUM(revenue_usd) FROM analytics").fetchone()
            return row[0] or 0.0

    def monthly_revenue(self, year: int, month: int) -> float:
        pattern = f"{year}-{month:02d}-%"
        with self._conn() as conn:
            row = conn.execute(
                "SELECT SUM(revenue_usd) FROM analytics WHERE date LIKE ?", (pattern,)
            ).fetchone()
            return row[0] or 0.0

    def channel_totals(self) -> dict:
        with self._conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_videos,
                    SUM(views) as total_views,
                    SUM(revenue_usd) as total_revenue
                FROM videos WHERE status = 'uploaded'
            """).fetchone()
            return dict(row) if row else {"total_videos": 0, "total_views": 0, "total_revenue": 0.0}
