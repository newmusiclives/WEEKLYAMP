"""Resend-to-non-openers campaign management routes."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from weeklyamp.web.deps import get_repo, render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def resend_campaigns_page(request: Request):
    """Main resend campaigns admin page.

    Shows published issues with open-rate data and lets the admin
    create a resend campaign with an alternate subject line. Also
    lists existing campaigns and their statuses.
    """
    repo = get_repo()

    # Published issues with engagement data
    published = repo.get_published_issues(limit=30)
    issues_with_stats = []
    for issue in published:
        engagement = repo.get_engagement(issue["id"])
        non_opener_count = len(repo.get_non_openers(issue["id"]))
        issues_with_stats.append({
            **issue,
            "engagement": engagement,
            "non_opener_count": non_opener_count,
        })

    # Existing resend campaigns
    campaigns = repo.get_resend_campaigns(limit=20)

    return HTMLResponse(
        render(
            "resend_campaigns.html",
            issues=issues_with_stats,
            campaigns=campaigns,
        )
    )


@router.post("/create", response_class=HTMLResponse)
async def create_resend(
    request: Request,
    issue_id: int = Form(...),
    original_subject: str = Form(""),
    resend_subject: str = Form(...),
    delay_hours: int = Form(48),
):
    """Create a new resend campaign for non-openers of an issue."""
    repo = get_repo()

    # Validate issue exists and is published
    issue = repo.get_issue(issue_id)
    if not issue or issue.get("status") != "published":
        return HTMLResponse(
            '<div class="alert alert-danger">Issue not found or not published.</div>'
        )

    if not resend_subject.strip():
        return HTMLResponse(
            '<div class="alert alert-danger">Resend subject line is required.</div>'
        )

    # Count non-openers for target_count
    non_openers = repo.get_non_openers(issue_id)
    target_count = len(non_openers)

    campaign_id = repo.create_resend_campaign(
        issue_id=issue_id,
        original_subject=original_subject or issue.get("title", ""),
        resend_subject=resend_subject.strip(),
        delay_hours=delay_hours,
    )

    # Update the target_count
    repo.update_resend_campaign(campaign_id, target_count=target_count)

    return HTMLResponse(
        f'<div class="alert alert-success">'
        f'Resend campaign created for {target_count} non-openers '
        f'(issue #{issue.get("issue_number", "?")}).'
        f'</div>'
    )


@router.post("/cancel/{campaign_id}", response_class=HTMLResponse)
async def cancel_resend(campaign_id: int, request: Request):
    """Cancel a pending resend campaign."""
    repo = get_repo()
    campaign = repo.get_resend_campaign(campaign_id)
    if not campaign:
        return HTMLResponse(
            '<div class="alert alert-danger">Campaign not found.</div>'
        )
    if campaign["status"] != "pending":
        return HTMLResponse(
            '<div class="alert alert-warning">Only pending campaigns can be cancelled.</div>'
        )
    repo.update_resend_campaign(campaign_id, status="cancelled")
    return HTMLResponse(
        '<div class="alert alert-success">Campaign cancelled.</div>'
    )


@router.get("/non-openers/{issue_id}", response_class=HTMLResponse)
async def non_openers_detail(issue_id: int, request: Request):
    """HTMX partial: show the list of non-openers for an issue."""
    repo = get_repo()
    non_openers = repo.get_non_openers(issue_id)
    rows = "".join(
        f"<tr><td>{s['email']}</td><td>{s.get('first_name') or '—'}</td></tr>"
        for s in non_openers[:100]
    )
    if not rows:
        return HTMLResponse('<p class="text-muted">No non-openers found (or no tracking data yet).</p>')
    extra = ""
    if len(non_openers) > 100:
        extra = f'<p class="text-muted">Showing 100 of {len(non_openers)} non-openers.</p>'
    return HTMLResponse(
        f'<table class="data-table"><thead><tr><th>Email</th><th>Name</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>{extra}'
    )
