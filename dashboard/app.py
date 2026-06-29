"""Flask revenue dashboard for the faceless YouTube channel."""

import sys
import os
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request, send_file, abort

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
# pipeline instances keyed by video_id (for progress access)
_pipelines: dict[int, object] = {}

# holds pending OAuth flow between requests
_yt_flow = {}

# On startup: reset all in-progress statuses — those threads died with the container
_STUCK_STATUSES = ["uploading", "scripting", "scripted", "voiced", "thumbnailed", "produced"]
try:
    for _stuck in _STUCK_STATUSES:
        for v in db.list_videos(status=_stuck, limit=100):
            db.update_video(v["id"], status="error")
except Exception:
    pass


def _yt_token_path():
    return Path(__file__).parent.parent / "credentials" / "token.pickle"


def _yt_connected():
    return _yt_token_path().exists()


def _yt_status():
    try:
        from src.uploader import YouTubeUploader
        YouTubeUploader()._get_service()
        return "connected"
    except Exception as e:
        return str(e)


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
    yt_status = _yt_status()
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
        yt_status=yt_status,
        jobs=_jobs,
    )


# ── Generate video (runs pipeline in background thread) ──────────────────────

@app.route("/generate", methods=["POST"])
def generate():
    topic  = request.form.get("topic", "").strip()
    niche  = request.form.get("niche", "personal_finance")
    mode   = request.form.get("mode", "speed")   # speed | full | dry_run

    if not topic:
        from src.topics import get_trending_topics
        topic = get_trending_topics(niche, count=1)[0]

    # create DB row now so we can show it immediately
    video_id = db.create_video(topic, niche)
    _jobs[video_id] = "running"

    def _run():
        try:
            from src.pipeline import Pipeline
            speed_mode  = (mode == "speed")
            dry_run     = (mode == "dry_run")
            skip_upload = (mode in ("dry_run",))
            pipeline    = Pipeline(skip_upload=skip_upload, dry_run=dry_run, speed_mode=speed_mode)
            _pipelines[video_id] = pipeline
            pipeline.run_topic(topic, niche, video_id=video_id)
            _jobs[video_id] = "done"
        except Exception as e:
            _jobs[video_id] = f"error: {e}"
            db.update_video(video_id, status="error")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "video_id": video_id, "topic": topic})


# ── Job status polling ────────────────────────────────────────────────────────

@app.route("/api/job/<int:video_id>")
def job_status(video_id):
    status   = _jobs.get(video_id, "unknown")
    video    = db.get_video(video_id)
    pipeline = _pipelines.get(video_id)
    progress = pipeline.progress.get(video_id, {"step": "", "pct": 0}) if pipeline else {"step": "", "pct": 0}
    return jsonify({"job": status, "video": video, "progress": progress})


@app.route("/api/upload/<int:video_id>", methods=["POST"])
def api_upload(video_id):
    """Upload a produced video, or re-run full pipeline if file is missing."""
    video = db.get_video(video_id)
    if not video:
        return jsonify({"ok": False, "error": "Video not found"}), 404

    video_path = video.get("video_path") or ""
    file_ok = video_path and Path(video_path).exists()

    _jobs[video_id] = "running"

    def _do():
        try:
            from src.pipeline import Pipeline
            p = Pipeline(skip_upload=False, dry_run=False, speed_mode=True)
            _pipelines[video_id] = p
            if file_ok:
                p._do_upload(video_id)
            else:
                # File gone (container restart) — rebuild everything then upload
                topic = video.get("topic") or ""
                niche = video.get("niche") or "personal_finance"
                p.run_topic(topic, niche, video_id=video_id)
            _jobs[video_id] = "done"
        except Exception as e:
            _jobs[video_id] = f"error: {e}"
            db.update_video(video_id, status="error")

    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"ok": True, "video_id": video_id})


@app.route("/api/retry/<int:video_id>", methods=["POST"])
def api_retry(video_id):
    """Full pipeline re-run for a stuck/error/thumbnailed video."""
    video = db.get_video(video_id)
    if not video:
        return jsonify({"ok": False, "error": "Video not found"}), 404

    topic = video.get("topic") or ""
    niche = video.get("niche") or "personal_finance"
    if not topic:
        return jsonify({"ok": False, "error": "No topic saved for this video"}), 400

    _jobs[video_id] = "running"

    def _do():
        try:
            from src.pipeline import Pipeline
            p = Pipeline(skip_upload=False, dry_run=False, speed_mode=True)
            _pipelines[video_id] = p
            p.run_topic(topic, niche, video_id=video_id)
            _jobs[video_id] = "done"
        except Exception as e:
            _jobs[video_id] = f"error: {e}"
            db.update_video(video_id, status="error")

    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"ok": True, "video_id": video_id})


@app.route("/api/run-all", methods=["POST"])
def api_run_all():
    """Kick off full pipeline for every non-uploaded video, staggered to avoid rate limits."""
    import time as _time
    all_videos = db.list_videos(limit=100)
    skipped_statuses = {"uploaded", "uploading"}
    queue = []
    for video in all_videos:
        vid_id = video["id"]
        status = video.get("status") or "pending"
        if status in skipped_statuses:
            continue
        if _jobs.get(vid_id) == "running":
            continue
        topic = video.get("topic") or ""
        niche  = video.get("niche") or "personal_finance"
        if not topic:
            continue
        _jobs[vid_id] = "running"
        queue.append((vid_id, topic, niche))

    def _run_queue(items):
        for idx, (v_id, t, n) in enumerate(items):
            if idx > 0:
                _time.sleep(8)  # 8s gap between starts — avoids Groq rate limits
            try:
                from src.pipeline import Pipeline
                p = Pipeline(skip_upload=False, dry_run=False, speed_mode=True)
                _pipelines[v_id] = p
                p.run_topic(t, n, video_id=v_id)
                _jobs[v_id] = "done"
            except Exception as e:
                _jobs[v_id] = f"error: {e}"
                db.update_video(v_id, status="error")

    threading.Thread(target=_run_queue, args=(queue,), daemon=True).start()
    return jsonify({"ok": True, "count": len(queue)})


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


@app.route("/download/<int:video_id>/<file_type>")
def download_file(video_id, file_type):
    video = db.get_video(video_id)
    if not video:
        abort(404)

    path_map = {
        "video":     video.get("video_path"),
        "audio":     video.get("audio_path"),
        "thumbnail": video.get("thumb_path"),
        "script":    video.get("script_path"),
    }
    file_path = path_map.get(file_type)
    if not file_path or not Path(file_path).exists():
        abort(404)

    return send_file(file_path, as_attachment=True)


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/api/test-youtube")
def api_test_youtube():
    """Check if YouTube credentials are valid and return status."""
    try:
        from src.uploader import YouTubeUploader
        u = YouTubeUploader()
        u._get_service()
        return jsonify({"ok": True, "status": "connected"})
    except Exception as e:
        return jsonify({"ok": False, "status": "disconnected", "error": str(e)})


@app.route("/youtube-auth")
def youtube_auth():
    secrets = Path(__file__).parent.parent / "credentials" / "client_secrets.json"
    if not secrets.exists():
        return ("<h2 style='font-family:sans-serif;color:red'>client_secrets.json not found."
                " Upload it to the credentials/ folder first.</h2>"), 400
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            str(secrets), ["https://www.googleapis.com/auth/youtube.upload"]
        )
        flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        _yt_flow["flow"] = flow
    except Exception as e:
        return f"<h2>Error: {e}</h2>", 500
    connected = _yt_connected()
    return render_template("youtube_auth.html", auth_url=auth_url, connected=connected, error=None, success=False)


@app.route("/youtube-auth/connect", methods=["POST"])
def youtube_auth_connect():
    import pickle
    code = request.form.get("code", "").strip()
    flow = _yt_flow.get("flow")
    if not flow or not code:
        return "<h2>Missing code or session expired. <a href='/youtube-auth'>Try again</a></h2>", 400
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        tp = _yt_token_path()
        tp.parent.mkdir(parents=True, exist_ok=True)
        with open(tp, "wb") as f:
            pickle.dump(creds, f)
        import base64
        token_b64 = base64.b64encode(pickle.dumps(creds)).decode()
        return render_template("youtube_auth.html", auth_url=None, connected=True,
                               error=None, success=True, token_b64=token_b64)
    except Exception as e:
        return render_template("youtube_auth.html", auth_url=None, connected=False,
                               error=str(e), success=False, token_b64=None)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
