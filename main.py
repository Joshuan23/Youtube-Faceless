#!/usr/bin/env python3
"""
Twinkle Tots – Faceless Nursery Rhyme Channel Automation
Usage: python main.py --help
"""

import os
import sys
import logging
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

load_dotenv()

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("output/pipeline.log"),
    ],
)
Path("output").mkdir(exist_ok=True)


@click.group()
def cli():
    """Twinkle Tots – Faceless Nursery Rhyme Channel Automation"""


# ── produce ─────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--topic", "-t", default=None, help="Specific video topic")
@click.option("--niche", "-n", default=None, help="Style: nursery_rhymes | lullabies | learning_songs")
@click.option("--count", "-c", default=1, show_default=True, help="Number of videos to produce")
@click.option("--skip-upload", is_flag=True, help="Skip YouTube upload step")
@click.option("--dry-run", is_flag=True, help="Script + SEO only (no TTS/video render)")
def produce(topic, niche, count, skip_upload, dry_run):
    """Produce one or more YouTube videos end-to-end."""
    from src.pipeline import Pipeline

    pipeline = Pipeline(skip_upload=skip_upload, dry_run=dry_run)
    if dry_run:
        console.print("[yellow]Dry-run mode: script + SEO only[/yellow]")

    if topic:
        niche = niche or pipeline.config["channel"]["niche"]
        with console.status(f"[bold green]Producing: {topic}[/bold green]"):
            vid_id = pipeline.run_topic(topic, niche)
        _print_video_result(pipeline.db.get_video(vid_id))
    else:
        niche = niche or pipeline.config["channel"]["niche"]
        with console.status(f"[bold green]Producing {count} video(s) for niche: {niche}[/bold green]"):
            ids = pipeline.run_batch(count=count, niche=niche)
        for vid_id in ids:
            _print_video_result(pipeline.db.get_video(vid_id))


# ── schedule ─────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--niche", "-n", default=None)
def schedule(niche):
    """Start the automated daily posting scheduler."""
    from src.pipeline import Pipeline
    from src.scheduler import run_daily_pipeline

    pipeline = Pipeline()
    niche = niche or pipeline.config["channel"]["niche"]

    def run(n):
        pipeline.run_batch(count=1, niche=n)

    console.print(f"[bold green]Scheduler started for niche:[/bold green] {niche}")
    run_daily_pipeline(run, niche=niche)


# ── analytics ────────────────────────────────────────────────────────────────


@cli.command()
def analytics():
    """Show channel analytics and $10k/month projection."""
    from src.analytics import Analytics
    from src.database import Database

    a = Analytics(Database())
    console.print(a.format_dashboard())

    path = a.videos_needed_for_target()
    console.print()
    console.print("[bold]Path to $10,000/month:[/bold]")
    console.print(f"  Monthly views needed:  [cyan]{path['monthly_views_needed']:,}[/cyan]")
    console.print(f"  Videos needed:         [cyan]{path['videos_needed_in_catalog']}[/cyan]")
    console.print(f"  Weeks to build (5x/wk):[cyan]{path['weeks_to_build_at_5x_week']}[/cyan]")
    console.print(f"  Months to build:       [cyan]{path['months_to_build']}[/cyan]")


# ── dashboard ────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--port", default=5000, show_default=True)
def dashboard(port):
    """Launch the web revenue dashboard."""
    console.print(f"[bold green]Dashboard running at:[/bold green] http://localhost:{port}")
    os.environ["PORT"] = str(port)
    from dashboard.app import app
    app.run(host="0.0.0.0", port=port, debug=False)


# ── topics ───────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--niche", "-n", default="nursery_rhymes")
@click.option("--count", "-c", default=10, show_default=True)
def topics(niche, count):
    """List nursery-rhyme/song ideas for a style."""
    from src.topics import get_trending_topics

    with console.status("Fetching topics…"):
        ideas = get_trending_topics(niche, count=count)

    t = Table(title=f"Topic Ideas – {niche}", show_lines=True)
    t.add_column("#", style="dim", width=4)
    t.add_column("Topic", style="bold")
    for i, idea in enumerate(ideas, 1):
        t.add_row(str(i), idea)
    console.print(t)


# ── thumbnail ────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("title")
@click.option("--topic", default="")
@click.option("--output", "-o", default="output/thumbnails/preview.jpg")
def thumbnail(title, topic, output):
    """Generate a thumbnail for a given title."""
    from src.thumbnail import ThumbnailCreator

    tc = ThumbnailCreator()
    paths = tc.create_ab_set(title, topic, "output/thumbnails")
    for p in paths:
        console.print(f"[green]Created:[/green] {p}")


# ── status ───────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--limit", default=10, show_default=True)
def status(limit):
    """Show recent video production status."""
    from src.database import Database

    db = Database()
    videos = db.list_videos(limit=limit)
    if not videos:
        console.print("[yellow]No videos found. Run 'python main.py produce' to get started.[/yellow]")
        return

    t = Table(title="Recent Videos", show_lines=False)
    t.add_column("ID", width=4, style="dim")
    t.add_column("Title", max_width=45)
    t.add_column("Status", width=12)
    t.add_column("Views", width=8)
    t.add_column("Revenue", width=10)
    t.add_column("YouTube", width=30)

    status_colors = {
        "uploaded": "green",
        "produced": "blue",
        "scripted": "yellow",
        "pending": "dim",
        "error": "red",
    }
    for v in videos:
        color = status_colors.get(v["status"], "white")
        t.add_row(
            str(v["id"]),
            (v["title"] or v["topic"])[:45],
            f"[{color}]{v['status']}[/{color}]",
            f"{v['views']:,}",
            f"${v['revenue_usd']:.2f}",
            v.get("youtube_url") or "–",
        )
    console.print(t)


# ── helpers ───────────────────────────────────────────────────────────────────


def _print_video_result(video: dict):
    if not video:
        return
    rprint(f"\n[bold green]✓ Video ready[/bold green] (id={video['id']})")
    rprint(f"  Title:   [cyan]{video.get('title') or video.get('topic')}[/cyan]")
    rprint(f"  Status:  [yellow]{video['status']}[/yellow]")
    if video.get("youtube_url"):
        rprint(f"  URL:     [blue]{video['youtube_url']}[/blue]")


if __name__ == "__main__":
    cli()
