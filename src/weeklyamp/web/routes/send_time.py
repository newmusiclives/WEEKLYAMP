"""Admin routes for Send-Time Optimization (STO) dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from weeklyamp.web.deps import get_repo, render

router = APIRouter()


@router.get("/")
async def send_time_dashboard(request: Request):
    """Display the STO dashboard with histogram and subscriber table."""
    repo = get_repo()

    from weeklyamp.delivery.send_time_optimizer import get_send_time_distribution

    distribution = get_send_time_distribution(repo)
    subscribers = repo.get_subscriber_send_times(limit=50)
    stats = repo.get_send_time_stats()

    total_profiled = sum(row["subscriber_count"] for row in distribution)
    max_count = max((row["subscriber_count"] for row in distribution), default=1) or 1

    return HTMLResponse(render(
        "send_time_dashboard.html",
        distribution=distribution,
        subscribers=subscribers,
        stats=stats,
        total_profiled=total_profiled,
        max_count=max_count,
    ))


@router.post("/refresh")
async def refresh_send_times(request: Request):
    """Trigger a full refresh of all subscriber send-time profiles."""
    repo = get_repo()

    from weeklyamp.delivery.send_time_optimizer import refresh_all_send_times

    updated = refresh_all_send_times(repo)

    # Check if this is an HTMX request
    if request.headers.get("HX-Request"):
        distribution = []
        from weeklyamp.delivery.send_time_optimizer import get_send_time_distribution
        distribution = get_send_time_distribution(repo)
        subscribers = repo.get_subscriber_send_times(limit=50)
        stats = repo.get_send_time_stats()
        total_profiled = sum(row["subscriber_count"] for row in distribution)
        max_count = max((row["subscriber_count"] for row in distribution), default=1) or 1
        return HTMLResponse(render(
            "send_time_dashboard.html",
            distribution=distribution,
            subscribers=subscribers,
            stats=stats,
            total_profiled=total_profiled,
            max_count=max_count,
            refresh_message=f"Refreshed send times for {updated} subscribers.",
        ))

    return RedirectResponse("/admin/send-times/", status_code=303)
