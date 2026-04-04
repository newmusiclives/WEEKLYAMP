"""Dashboard route — main overview page."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()


def _generate_insights(repo, config) -> list[dict]:
    """Generate contextual dashboard insights."""
    insights: list[dict] = []
    subscriber_count = repo.get_subscriber_count()

    # Subscriber insights
    if subscriber_count == 0:
        insights.append({
            "icon": "&#128101;",
            "title": "No subscribers yet",
            "message": "Import your first subscribers via CSV or share your subscribe link to get started.",
            "action_url": "/subscribers/import",
            "action_label": "Import Subscribers",
            "type": "warning",
        })
    elif subscriber_count < 100:
        insights.append({
            "icon": "&#128200;",
            "title": f"{subscriber_count} subscribers — growing!",
            "message": "Focus on cross-promotion and referrals to reach your first 100.",
            "action_url": "/admin/marketing/automation",
            "action_label": "Growth Tactics",
            "type": "info",
        })
    else:
        insights.append({
            "icon": "&#127881;",
            "title": f"{subscriber_count:,} subscribers",
            "message": "Your audience is growing. Consider launching paid tiers or selling sponsor slots.",
            "action_url": "/admin/revenue",
            "action_label": "Revenue Dashboard",
            "type": "success",
        })

    # Content insights
    try:
        issues = repo.get_published_issues(limit=1)
        if not issues:
            insights.append({
                "icon": "&#128240;",
                "title": "No issues published yet",
                "message": "Follow the setup wizard to publish your first newsletter issue.",
                "action_url": "/admin/setup/wizard",
                "action_label": "Setup Wizard",
                "type": "warning",
            })
    except Exception:
        pass

    # Sponsor insights
    try:
        revenue = repo.get_revenue_summary()
        sponsor = revenue.get("sponsor", {})
        if sponsor.get("total_bookings", 0) == 0:
            insights.append({
                "icon": "&#128176;",
                "title": "No sponsor bookings yet",
                "message": "Use the AI CMO to identify prospects and draft outreach emails.",
                "action_url": "/admin/marketing/automation",
                "action_label": "Scan for Prospects",
                "type": "info",
            })
        elif sponsor.get("pipeline_cents", 0) > 0:
            pipeline = sponsor["pipeline_cents"] / 100
            insights.append({
                "icon": "&#128176;",
                "title": f"${pipeline:,.0f} in sponsor pipeline",
                "message": f"{sponsor.get('total_bookings', 0)} bookings in progress. Follow up on pending deals.",
                "action_url": "/sponsor-blocks",
                "action_label": "Manage Sponsors",
                "type": "success",
            })
    except Exception:
        pass

    # Agent insights
    try:
        pending_tasks = repo.get_tasks_for_review()
        if pending_tasks:
            insights.append({
                "icon": "&#129302;",
                "title": f"{len(pending_tasks)} tasks awaiting review",
                "message": "Your AI staff has completed work that needs your approval.",
                "action_url": "/agents/tasks",
                "action_label": "Review Tasks",
                "type": "info",
            })
    except Exception:
        pass

    # Marketing insights
    try:
        prospects = repo.get_sponsor_prospects(status="contacted")
        if prospects:
            overdue = [p for p in prospects if p.get("next_followup_at")]
            if overdue:
                insights.append({
                    "icon": "&#128222;",
                    "title": f"{len(overdue)} prospects need follow-up",
                    "message": "Contacted prospects are waiting for a response.",
                    "action_url": "/admin/marketing/prospects",
                    "action_label": "View Pipeline",
                    "type": "warning",
                })
    except Exception:
        pass

    return insights


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    cfg = get_config()
    repo = get_repo()
    issue = repo.get_current_issue()
    sections = repo.get_active_sections()
    counts = repo.get_table_counts()

    drafts = []
    draft_map = {}
    if issue:
        drafts = repo.get_drafts_for_issue(issue["id"])
        draft_map = {d["section_slug"]: d for d in drafts}

    approved = sum(1 for d in drafts if d["status"] == "approved")
    pending = sum(1 for d in drafts if d["status"] == "pending")
    rejected = sum(1 for d in drafts if d["status"] == "rejected")

    # Sponsor stats for current issue
    sponsor_stats = None
    if issue:
        blocks = repo.get_sponsor_blocks_for_issue(issue["id"])
        bookings = repo.get_bookings_for_issue(issue["id"])
        booked = len(blocks) + len(bookings)
        sponsor_stats = {
            "booked": booked,
            "open": max(0, cfg.sponsor_slots.max_per_issue - booked),
        }

    # Upcoming sends (multi-frequency)
    upcoming_sends = repo.get_upcoming_issues(limit=12)

    # Load editions for display
    editions = repo.get_editions()

    # Smart insights
    insights = _generate_insights(repo, cfg)

    return render("dashboard.html",
        config=cfg,
        issue=issue,
        sections=sections,
        draft_map=draft_map,
        counts=counts,
        stats={"approved": approved, "pending": pending, "rejected": rejected, "total": len(sections)},
        sponsor_stats=sponsor_stats,
        upcoming_sends=upcoming_sends if len(upcoming_sends) > 1 else [],
        editions=editions,
        insights=insights,
    )
