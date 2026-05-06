"""Subscriber preference center (public, subscriber-facing)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from weeklyamp.web.deps import get_config, get_repo, render
from weeklyamp.web.security import rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)

# Defense-in-depth on bearer-token routes: the unsubscribe_token is
# 256-bit random so brute force is infeasible mathematically, but
# rate-limiting still pays off — it bounds the cost of a stolen token
# being used in an automated scrape and surfaces probing attempts in
# the rate_limits table for monitoring. 30/min comfortably covers a
# legitimate subscriber clicking through the preference center.
_TOKEN_RATE_LIMIT = Depends(rate_limit("subscriber_token", max_per_minute=30))


def _validate_token(token: str):
    """Look up subscriber by their bearer token. Returns subscriber dict or None.

    The lookup key is ``unsubscribe_token`` — a 256-bit url-safe random
    string set at signup (`subscribe.py:144`). It serves as a unified
    bearer secret across `/unsubscribe`, `/my-dashboard/{token}`,
    `/preferences/{token}`, and `/refer/dashboard/{token}` — they all
    have the same threat model (token leak = full account access)
    so sharing one secret per subscriber keeps emails simple and
    avoids a separate per-feature token table.

    Previously this queried a `preference_token` column that does not
    exist in the schema, so every preference link 500'd in production.
    """
    if not token:
        return None
    repo = get_repo()
    conn = repo._conn()
    row = conn.execute(
        "SELECT * FROM subscribers WHERE unsubscribe_token = ? AND status = 'active'",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


@router.get("/preferences/{token}", response_class=HTMLResponse, dependencies=[_TOKEN_RATE_LIMIT])
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


@router.post("/preferences/{token}", response_class=HTMLResponse, dependencies=[_TOKEN_RATE_LIMIT])
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
        # Preferences (frequency / timezone / interests) live in the
        # `subscriber_preferences` table, edition subscriptions in
        # `subscriber_editions`. The previous implementation tried to
        # update flat columns on `subscribers` that do not exist,
        # which 500'd in production. Use the proper normalised
        # repo helpers instead.
        repo.upsert_subscriber_preferences(
            subscriber_id=subscriber["id"],
            content_frequency=content_frequency,
            timezone=timezone,
            interests=interests.strip(),
        )
        send_days_csv = ",".join(send_days) if send_days else "monday,wednesday,saturday"
        repo.set_subscriber_editions(
            subscriber["id"], editions, send_days_csv=send_days_csv,
        )

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


@router.get("/my-dashboard/{token}", response_class=HTMLResponse, dependencies=[_TOKEN_RATE_LIMIT])
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


@router.get("/my-dashboard/{token}/export", dependencies=[_TOKEN_RATE_LIMIT])
async def subscriber_data_export(token: str, request: Request):
    """GDPR Article 20 — Right to data portability.

    Returns a JSON dump of every record we hold about the subscriber,
    keyed off the unsubscribe_token (which serves as a per-subscriber
    bearer secret). Includes profile, preferences, edition subscriptions,
    referral data, milestones, and tracking events.
    """
    repo = get_repo()
    conn = repo._conn()
    sub_row = conn.execute(
        "SELECT * FROM subscribers WHERE unsubscribe_token = ?", (token,)
    ).fetchone()
    if not sub_row:
        conn.close()
        return JSONResponse({"error": "invalid token"}, status_code=404)
    sub = dict(sub_row)
    sub_id = sub["id"]

    def _query(sql: str, params=()):
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.debug("data export query failed: %s — %s", sql[:60], exc)
            return []

    bundle = {
        "export_format_version": 1,
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "subscriber": sub,
        "editions": _query(
            "SELECT ne.slug, ne.name, se.send_days FROM subscriber_editions se "
            "JOIN newsletter_editions ne ON ne.id = se.edition_id "
            "WHERE se.subscriber_id = ?",
            (sub_id,),
        ),
        "preferences": _query(
            "SELECT * FROM subscriber_preferences WHERE subscriber_id = ?",
            (sub_id,),
        ),
        "genres": _query(
            "SELECT genre FROM subscriber_genres WHERE subscriber_id = ?",
            (sub_id,),
        ),
        "milestones": _query(
            "SELECT * FROM newsletter_milestones WHERE subscriber_id = ?",
            (sub_id,),
        ),
        "tracking_events": _query(
            "SELECT event_type, issue_id, occurred_at FROM email_tracking_events "
            "WHERE subscriber_id = ? ORDER BY occurred_at DESC LIMIT 1000",
            (sub_id,),
        ),
        "referral_log": _query(
            "SELECT * FROM referral_log WHERE referrer_subscriber_id = ?",
            (sub_id,),
        ),
        "audit_note": (
            "This export was generated under GDPR Article 20 (right to data "
            "portability) and CCPA right-to-know. To request deletion, "
            "use the unsubscribe link or contact privacy@truefansnewsletters.com."
        ),
    }
    conn.close()

    headers = {
        "Content-Disposition": (
            f'attachment; filename="truefansdispatch-data-{sub_id}.json"'
        ),
    }
    return JSONResponse(bundle, headers=headers)
