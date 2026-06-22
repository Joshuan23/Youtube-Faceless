"""Flask revenue dashboard for the faceless YouTube channel."""

import sys
import os
from pathlib import Path

# allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, redirect, url_for, request
from src.database import Database
from src.analytics import Analytics
from src.scheduler import next_upload_times

app = Flask(__name__)
db = Database()
analytics = Analytics(db)


@app.route("/")
def index():
    summary = analytics.monthly_summary()
    stats = analytics.content_calendar_stats()
    videos = db.list_videos(limit=20)
    upload_times = [t.strftime("%a %b %d, %H:%M UTC") for t in next_upload_times(5)]
    proj = analytics.revenue_projection(
        current_videos=stats["uploaded"],
        avg_views_per_video=50_000,
    )
    path_data = analytics.videos_needed_for_target()
    return render_template(
        "index.html",
        summary=summary,
        stats=stats,
        videos=videos,
        upload_times=upload_times,
        projections=proj["projections"][:6],
        months_to_target=proj.get("months_to_target"),
        path_data=path_data,
    )


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "summary": analytics.monthly_summary(),
        "pipeline": analytics.content_calendar_stats(),
        "projection": analytics.revenue_projection(
            current_videos=analytics.content_calendar_stats()["uploaded"],
            avg_views_per_video=50_000,
        ),
    })


@app.route("/api/videos")
def api_videos():
    limit = int(request.args.get("limit", 50))
    status = request.args.get("status")
    return jsonify(db.list_videos(status=status, limit=limit))


@app.route("/api/record_revenue", methods=["POST"])
def record_revenue():
    data = request.json
    db.record_analytics(
        video_id=data["video_id"],
        date=data["date"],
        views=data.get("views", 0),
        revenue_usd=data.get("revenue_usd", 0.0),
        cpm=data.get("cpm", 0.0),
        ctr=data.get("ctr", 0.0),
        watch_time_hrs=data.get("watch_time_hrs", 0.0),
    )
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
