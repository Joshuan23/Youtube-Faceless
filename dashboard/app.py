"""Flask revenue dashboard for the faceless YouTube channel."""

import sys
import os
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request

# Guard every src import — missing optional packages won't crash the dashboard
try:
    from src.database import Database
    from src.analytics import Analytics
    from src.scheduler import next_upload_times
    from src.llm import active_provider
except Exception as _e:
    print(f"[warn] Import issue: {_e}")
    # minimal stubs so the app still starts
    class Database:
        def list_videos(self, **kw): return []
        def create_video(self, t, n): return 1
        def get_video(self, i): return None
        def update_video(self, *a, **kw): pass
        def record_analytics(self, *a, **kw): pass
    class Analytics:
        def __init__(self, *a): pass
        def monthly_summary(self): return {"monthly_revenue_usd": 0, "total_revenue_usd": 0, "total_views": 0}
        def content_calendar_stats(self): return {"pending":0,"scripted":0,"produced":0,"uploaded":0}
        def revenue_projection(self, **kw): return {"projections": [], "months_to_target": None}
        def videos_needed_for_target(self): return {}
    def next_upload_times(n=5): return []
    def active_provider(): return "none"

app = Flask(__name__)
db = Database()
analytics = Analytics(db)

# tracks background jobs: {video_id: "running"|"done"|"error: ..."}
_jobs: dict[int, str] = {}


@app.route("/")
def index():
    summary   = analytics.monthly_summary()
    stats     = analytics.content_calendar_stats()
    videos    = db.list_videos(limit=20)
    upload_times = [t.strftime("%a %b %d, %H:%M UTC") for t in next_upload_times(5)]
    proj      = analytics.revenue_projection(
        current_videos=stats["uploaded"], avg_views_per_video=50_000
    )
    provider  = active_provider()
    return render_template(
        "index.html",
        summary=summary,
        stats=stats,
        videos=videos,
        upload_times=upload_times,
        projections=proj["projections"][:6],
        months_to_target=proj.get("months_to_target"),
        path_data=analytics.videos_needed_for_target(),
        llm_provider=provider,
        jobs=_jobs,
    )


# ── Generate video (runs pipeline in background thread) ──────────────────────

@app.route("/generate", methods=["POST"])
def generate():
    topic  = request.form.get("topic", "").strip()
    niche  = request.form.get("niche", "personal_finance")
    mode   = request.form.get("mode", "dry_run")   # dry_run | full

    if not topic:
        from src.topics import get_trending_topics
        topic = get_trending_topics(niche, count=1)[0]

    # create DB row now so we can show it immediately
    video_id = db.create_video(topic, niche)
    _jobs[video_id] = "running"

    def _run():
        try:
            from src.pipeline import Pipeline
            skip_upload = True          # always skip upload from dashboard
            dry_run     = (mode == "dry_run")
            pipeline    = Pipeline(skip_upload=skip_upload, dry_run=dry_run)
            pipeline.run_topic(topic, niche)
            _jobs[video_id] = "done"
        except Exception as e:
            _jobs[video_id] = f"error: {e}"
            db.update_video(video_id, status="error")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "video_id": video_id, "topic": topic})


# ── Job status polling ────────────────────────────────────────────────────────

@app.route("/api/job/<int:video_id>")
def job_status(video_id):
    status = _jobs.get(video_id, "unknown")
    video  = db.get_video(video_id)
    return jsonify({"job": status, "video": video})


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "summary":    analytics.monthly_summary(),
        "pipeline":   analytics.content_calendar_stats(),
        "projection": analytics.revenue_projection(
            current_videos=analytics.content_calendar_stats()["uploaded"],
            avg_views_per_video=50_000,
        ),
    })


@app.route("/api/videos")
def api_videos():
    limit  = int(request.args.get("limit", 50))
    status = request.args.get("status")
    return jsonify(db.list_videos(status=status, limit=limit))


@app.route("/video/<int:video_id>")
def view_script(video_id):
    video = db.get_video(video_id)
    if not video:
        return "Video not found", 404

    # load script text and meta JSON
    script_text, meta = "", {}
    script_path = video.get("script_path") or ""
    if script_path and Path(script_path).exists():
        script_text = Path(script_path).read_text()

    import json
    meta_path = script_path.replace(".txt", "_meta.json") if script_path else ""
    if meta_path and Path(meta_path).exists():
        try:
            meta = json.loads(Path(meta_path).read_text())
        except Exception:
            pass

    seo   = meta.get("seo", {})
    title = seo.get("recommended_title") or video.get("title") or video.get("topic")
    desc  = seo.get("description", "")
    tags  = seo.get("tags", [])

    return render_template("script.html",
        video=video, title=title, script=script_text,
        description=desc, tags=tags, seo=seo)


@app.route("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
