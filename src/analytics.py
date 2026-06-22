"""Channel analytics, revenue tracking, and $10k/month projections."""

import math
from datetime import date, timedelta
from .database import Database


class Analytics:
    def __init__(self, db: Database = None):
        self.db = db or Database()

    def monthly_summary(self, year: int = None, month: int = None) -> dict:
        today = date.today()
        year = year or today.year
        month = month or today.month
        revenue = self.db.monthly_revenue(year, month)
        totals = self.db.channel_totals()
        return {
            "year": year,
            "month": month,
            "monthly_revenue_usd": round(revenue, 2),
            "total_videos": totals["total_videos"] or 0,
            "total_views": totals["total_views"] or 0,
            "total_revenue_usd": round(totals["total_revenue"] or 0.0, 2),
        }

    def revenue_projection(
        self,
        avg_cpm: float = 18.0,
        current_videos: int = 0,
        avg_views_per_video: int = 0,
        growth_rate_pct: float = 15.0,
        target_usd: float = 10_000.0,
    ) -> dict:
        """
        Project how many months to reach target monthly revenue.

        Uses a compounding growth model: each month views grow by growth_rate_pct.
        """
        monthly_views = current_videos * avg_views_per_video
        monthly_revenue = (monthly_views / 1000) * avg_cpm

        months_needed = None
        projections = []
        revenue = monthly_revenue
        for m in range(1, 37):  # up to 36 months
            revenue = revenue * (1 + growth_rate_pct / 100)
            projections.append({
                "month": m,
                "projected_monthly_revenue": round(revenue, 2),
                "projected_monthly_views": int((revenue / avg_cpm) * 1000),
            })
            if months_needed is None and revenue >= target_usd:
                months_needed = m

        return {
            "current_monthly_revenue_usd": round(monthly_revenue, 2),
            "target_monthly_revenue_usd": target_usd,
            "avg_cpm": avg_cpm,
            "growth_rate_pct": growth_rate_pct,
            "months_to_target": months_needed,
            "projections": projections[:12],  # show 12 months
        }

    def videos_needed_for_target(
        self, target_usd: float = 10_000.0, avg_cpm: float = 18.0, avg_views: int = 50_000
    ) -> dict:
        """How many videos / what channel size needed for $10k/month."""
        views_needed = (target_usd / avg_cpm) * 1000
        videos_needed = math.ceil(views_needed / avg_views)
        posts_per_week = 5
        weeks_to_build = math.ceil(videos_needed / posts_per_week)

        return {
            "monthly_views_needed": int(views_needed),
            "videos_needed_in_catalog": videos_needed,
            "weeks_to_build_at_5x_week": weeks_to_build,
            "months_to_build": round(weeks_to_build / 4.3, 1),
        }

    def content_calendar_stats(self) -> dict:
        """Return stats useful for the content calendar dashboard."""
        videos = self.db.list_videos(limit=200)
        pending = [v for v in videos if v["status"] == "pending"]
        scripted = [v for v in videos if v["status"] == "scripted"]
        produced = [v for v in videos if v["status"] == "produced"]
        uploaded = [v for v in videos if v["status"] == "uploaded"]
        return {
            "pending": len(pending),
            "scripted": len(scripted),
            "produced": len(produced),
            "uploaded": len(uploaded),
            "total": len(videos),
        }

    def format_dashboard(self) -> str:
        today = date.today()
        summary = self.monthly_summary(today.year, today.month)
        stats = self.content_calendar_stats()
        proj = self.revenue_projection(
            current_videos=stats["uploaded"],
            avg_views_per_video=50_000,
        )
        months = proj.get("months_to_target")
        months_str = f"{months} months" if months else ">36 months"

        lines = [
            "═" * 55,
            "  YOUTUBE CHANNEL ANALYTICS",
            "═" * 55,
            f"  Monthly Revenue:  ${summary['monthly_revenue_usd']:>10,.2f}",
            f"  Total Revenue:    ${summary['total_revenue_usd']:>10,.2f}",
            f"  Total Views:      {summary['total_views']:>12,}",
            f"  Videos Published: {stats['uploaded']:>12}",
            "─" * 55,
            "  PIPELINE",
            f"  Pending:          {stats['pending']:>12}",
            f"  Scripted:         {stats['scripted']:>12}",
            f"  Produced:         {stats['produced']:>12}",
            "─" * 55,
            "  PROJECTION TO $10K/MO",
            f"  ETA:              {months_str:>20}",
            f"  Current Monthly:  ${proj['current_monthly_revenue_usd']:>10,.2f}",
            "═" * 55,
        ]
        return "\n".join(lines)
