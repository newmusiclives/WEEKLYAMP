"""Subscriber preference center (public, subscriber-facing)."""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()
logger = logging.getLogger(__name__)


def _validate_token(token: str):
    """Look up subscriber by preference token. Returns subscriber dict or None."""
    repo = get_repo()
    conn = repo._conn()
    row = conn.execute(
        "SELECT * FROM subscribers WHERE preference_token = ? AND status = 'active'",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


@router.get("/preferences/{token}", response_class=HTMLResponse)
async def preferences_page(token: str):
    """Show preference form for a subscriber."""
    subscriber = _validate_token(token)
    if not subscriber:
        return HTMLResponse(
            "<html><body style='font-family:Inter,sans-serif;max-width:600px;margin:60px auto;text-align:center'>"
            "<h2>Invalid or expired link</h2>"
            "<p>This preference link is no longer valid. Please use the link from your most recent email.</p>"
            "</body></html>",
            status_code=404,
        )

    cfg = get_config()
    return render("preferences.html",
        subscriber=subscriber,
        token=token,
        newsletter_name=cfg.newsletter.name,
    )


@router.post("/preferences/{token}", response_class=HTMLResponse)
async def update_preferences(
    token: str,
    editions: list[str] = Form(default=[]),
    send_days: list[str] = Form(default=[]),
    content_frequency: str = Form("all"),
    timezone: str = Form("America/New_York"),
    interests: str = Form(""),
):
    """Update subscriber preferences."""
    subscriber = _validate_token(token)
    if not subscriber:
        return HTMLResponse(
            "<html><body style='font-family:Inter,sans-serif;max-width:600px;margin:60px auto;text-align:center'>"
            "<h2>Invalid or expired link</h2>"
            "<p>This preference link is no longer valid.</p>"
            "</body></html>",
            status_code=404,
        )

    try:
        repo = get_repo()
        conn = repo._conn()
        conn.execute(
            """UPDATE subscribers SET
               editions = ?,
               send_days = ?,
               content_frequency = ?,
               timezone = ?,
               interests = ?,
               updated_at = datetime('now')
               WHERE preference_token = ?""",
            (
                ",".join(editions),
                ",".join(send_days),
                content_frequency,
                timezone,
                interests.strip(),
                token,
            ),
        )
        conn.commit()
        conn.close()

        # Re-fetch updated subscriber
        subscriber = _validate_token(token)
        cfg = get_config()
        return render("preferences.html",
            subscriber=subscriber,
            token=token,
            newsletter_name=cfg.newsletter.name,
            message="Your preferences have been saved.",
            level="success",
        )
    except Exception as exc:
        logger.exception("Failed to update preferences for token=%s", token)
        cfg = get_config()
        return render("preferences.html",
            subscriber=subscriber,
            token=token,
            newsletter_name=cfg.newsletter.name,
            message=f"Failed to save preferences: {exc}",
            level="error",
        )


@router.get("/my-dashboard/{token}", response_class=HTMLResponse)
async def subscriber_dashboard(token: str, request: Request):
    repo = get_repo()
    config = get_config()
    # Look up subscriber by unsubscribe token
    conn = repo._conn()
    sub = conn.execute("SELECT * FROM subscribers WHERE unsubscribe_token = ?", (token,)).fetchone()
    conn.close()
    if not sub:
        return HTMLResponse("Invalid link", status_code=404)
    sub = dict(sub)

    # Get their editions
    editions_conn = repo._conn()
    editions = editions_conn.execute(
        """SELECT ne.name, ne.slug, se.send_days FROM subscriber_editions se
           JOIN newsletter_editions ne ON ne.id = se.edition_id
           WHERE se.subscriber_id = ?""", (sub["id"],)
    ).fetchall()
    editions_conn.close()
    editions = [dict(e) for e in editions]

    # Get milestones
    milestones = repo.get_subscriber_milestones(sub["id"])

    # Get referral stats
    referral_code = None
    try:
        referral_code = repo.get_referral_code(sub["id"])
    except Exception:
        pass

    return HTMLResponse(render("subscriber_dashboard.html",
        subscriber=sub, editions=editions, milestones=milestones,
        referral=referral_code, config=config, token=token))
