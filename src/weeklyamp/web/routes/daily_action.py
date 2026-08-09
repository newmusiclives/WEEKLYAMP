"""Routes for TrueFans Single Daily Action.

Two audiences in one module:

* ``/daily/*`` — public. Clicked straight from an email by a reader who
  has never logged in, so these routes are on both the public-prefix
  list and the coming-soon allow-list.
* ``/admin/daily-action*`` — the review desk: see what is queued, fix the
  copy, approve, regenerate, send.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from weeklyamp.content.daily_action import (
    PILLARS,
    build_daily_action,
    completion_count,
    get_issue_for_date,
    list_issues,
    mark_done,
    pillar_for_date,
    send_daily_action,
    set_status,
    should_send_on,
    streak_for_subscriber,
)
from weeklyamp.web.deps import get_config, get_repo
from weeklyamp.web.sanitize import sanitize_html
from weeklyamp.web.security import is_authenticated

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter()


def _require_admin(request: Request) -> Response | None:
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return None


def _parse_date(value: str) -> date:
    """Parse an ISO date, falling back to today on anything unparseable."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


# ---------------------------------------------------------------------
# Public — "Mark it done"
# ---------------------------------------------------------------------

_DONE_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Logged &mdash; TrueFans Single Daily Action</title></head>
<body style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             background:#f4f4f5;display:flex;align-items:center;justify-content:center;
             min-height:100vh;padding:24px;">
  <div style="max-width:420px;text-align:center;background:#fff;border-radius:12px;padding:40px 28px;">
    <div style="font-size:40px;line-height:1;margin-bottom:16px;">&#9889;</div>
    <h1 style="font-size:22px;margin:0 0 10px;color:#1a1a1a;">{heading}</h1>
    <p style="font-size:15px;line-height:1.55;color:#6b7280;margin:0;">{body}</p>
  </div>
</body></html>"""


@router.get("/daily/done/{issue_id}", response_class=HTMLResponse)
async def daily_done(issue_id: int, request: Request) -> Response:
    """Record that a reader completed today's action.

    The ``?s=`` parameter is the subscriber's existing unsubscribe token,
    reused here as a per-reader identifier so the streak can be attributed
    without minting a second token per subscriber. A click with no token
    (forwarded email, stripped query string) still counts as an anonymous
    completion rather than erroring.
    """
    repo = get_repo()
    token = (request.query_params.get("s") or "").strip()

    subscriber = None
    if token:
        try:
            subscriber = repo.get_subscriber_by_unsubscribe_token(token)
        except Exception:
            logger.exception("daily_done: token lookup failed")

    conn = repo._conn()
    try:
        row = conn.execute(
            "SELECT id, action_date FROM daily_action_issues WHERE id = ?",
            (issue_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return HTMLResponse(
            _DONE_PAGE.format(
                heading="We couldn&rsquo;t find that action",
                body="The link may have expired. Today&rsquo;s action is in your inbox.",
            ),
            status_code=404,
        )

    issue = dict(row)
    subscriber_id = subscriber["id"] if subscriber else None
    mark_done(
        repo,
        issue["id"],
        subscriber_id,
        issue["action_date"],
        request.client.host if request.client else "",
    )

    streak = streak_for_subscriber(repo, subscriber_id) if subscriber_id else 0
    if streak > 1:
        body = f"That&rsquo;s {streak} days in a row. Tomorrow&rsquo;s action lands in the morning."
    else:
        body = "Logged. Tomorrow&rsquo;s action lands in the morning."

    return HTMLResponse(
        _DONE_PAGE.format(heading="Done &mdash; nice work", body=body)
    )


# ---------------------------------------------------------------------
# Admin — review desk
# ---------------------------------------------------------------------

_STATUS_COLORS = {
    "draft": "#9ca3af",
    "approved": "#16a34a",
    "sent": "#1a1a1a",
    "skipped": "#dc2626",
}


def _render_admin(repo, config, message: str = "", error: str = "") -> str:
    issues = list_issues(repo, limit=30)
    today = date.today()

    conn = repo._conn()
    try:
        bank = conn.execute(
            """SELECT pillar, COUNT(*) AS total
               FROM daily_action_library
               WHERE is_active = 1
               GROUP BY pillar""",
        ).fetchall()
    finally:
        conn.close()
    bank_by_pillar = {dict(r)["pillar"]: dict(r)["total"] for r in bank}

    da = config.daily_action
    upcoming = []
    for offset in range(0, 7):
        d = today + timedelta(days=offset)
        if not should_send_on(d, da):
            continue
        existing = get_issue_for_date(repo, d)
        upcoming.append({
            "date": d,
            "pillar": pillar_for_date(d),
            "status": (existing or {}).get("status", "not built"),
            "subject": (existing or {}).get("subject", ""),
        })

    rows = []
    for issue in issues:
        color = _STATUS_COLORS.get(issue["status"], "#9ca3af")
        done = completion_count(repo, issue["id"])
        rows.append(
            f"<tr>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;white-space:nowrap;'>{issue['action_date']}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;'>"
            f"<span style='background:{PILLARS.get(issue['pillar'], {}).get('color', '#999')};color:#fff;"
            f"padding:2px 10px;border-radius:12px;font-size:11px;text-transform:uppercase;'>"
            f"{sanitize_html(issue['pillar'])}</span></td>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;'>{sanitize_html(issue['subject'])}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;color:{color};font-weight:600;'>"
            f"{sanitize_html(issue['status'])}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;text-align:right;'>{issue['recipients']}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;text-align:right;'>{done}</td>"
            f"<td style='padding:10px;border-bottom:1px solid #eee;white-space:nowrap;'>"
            f"<a href='/admin/daily-action/preview/{issue['id']}' target='_blank' "
            f"style='color:#7c5cfc;text-decoration:none;margin-right:10px;'>Preview</a>"
            + (
                f"<form method='post' action='/admin/daily-action/approve' style='display:inline;'>"
                f"<input type='hidden' name='issue_id' value='{issue['id']}'>"
                f"<button type='submit' style='background:#16a34a;color:#fff;border:none;"
                f"padding:5px 12px;border-radius:4px;cursor:pointer;font-size:12px;'>Approve</button>"
                f"</form>"
                if issue["status"] == "draft" else ""
            )
            + f"</td></tr>"
        )

    upcoming_rows = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'>{u['date'].strftime('%a %d %b')}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;'>{PILLARS.get(u['pillar'], {}).get('name', u['pillar'])}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;color:#6b7280;'>{sanitize_html(u['status'])}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;'>{sanitize_html(u['subject'])}</td></tr>"
        for u in upcoming
    )

    bank_rows = "".join(
        f"<span style='display:inline-block;margin:0 12px 8px 0;font-size:13px;color:#6b7280;'>"
        f"<strong style='color:#1a1a1a;'>{meta['name']}</strong> &middot; {bank_by_pillar.get(slug, 0)} actions</span>"
        for slug, meta in PILLARS.items()
    )

    banner = ""
    if message:
        banner = (f"<div style='background:#dcfce7;color:#166534;padding:12px 16px;"
                  f"border-radius:6px;margin-bottom:20px;'>{sanitize_html(message)}</div>")
    elif error:
        banner = (f"<div style='background:#fee2e2;color:#991b1b;padding:12px 16px;"
                  f"border-radius:6px;margin-bottom:20px;'>{sanitize_html(error)}</div>")

    enabled_note = "" if da.enabled else (
        "<div style='background:#fef3c7;color:#92400e;padding:12px 16px;border-radius:6px;"
        "margin-bottom:20px;'>The daily action is <strong>disabled</strong> in config "
        "(<code>daily_action.enabled</code>). Drafts can be built and previewed here, "
        "but nothing will send.</div>"
    )

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Single Daily Action &mdash; Admin</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             background:#f9fafb;margin:0;padding:32px 20px;color:#1a1a1a;">
<div style="max-width:1000px;margin:0 auto;">
  <a href="/dashboard" style="color:#6b7280;text-decoration:none;font-size:14px;">&larr; Dashboard</a>
  <h1 style="font-size:26px;margin:12px 0 6px;">TrueFans Single Daily Action</h1>
  <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">
    One action per day. Pillar rotates by weekday; copy is drafted from the action bank.</p>
  {banner}{enabled_note}

  <div style="background:#fff;border-radius:8px;padding:20px;margin-bottom:24px;">
    <h2 style="font-size:16px;margin:0 0 12px;">Action bank</h2>
    <div>{bank_rows}</div>
  </div>

  <div style="background:#fff;border-radius:8px;padding:20px;margin-bottom:24px;">
    <h2 style="font-size:16px;margin:0 0 12px;">Next 7 days</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">{upcoming_rows}</table>
    <form method="post" action="/admin/daily-action/build" style="margin-top:16px;">
      <button type="submit" style="background:#7c5cfc;color:#fff;border:none;padding:9px 18px;
              border-radius:6px;cursor:pointer;font-size:14px;">Build missing drafts</button>
    </form>
  </div>

  <div style="background:#fff;border-radius:8px;padding:20px;">
    <h2 style="font-size:16px;margin:0 0 12px;">Recent</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr style="text-align:left;color:#6b7280;font-size:12px;text-transform:uppercase;">
        <th style="padding:10px;">Date</th><th style="padding:10px;">Pillar</th>
        <th style="padding:10px;">Subject</th><th style="padding:10px;">Status</th>
        <th style="padding:10px;text-align:right;">Sent</th>
        <th style="padding:10px;text-align:right;">Done</th>
        <th style="padding:10px;"></th>
      </tr>
      {"".join(rows) or "<tr><td style='padding:16px;color:#9ca3af;' colspan='7'>Nothing built yet.</td></tr>"}
    </table>
  </div>
</div></body></html>"""


@admin_router.get("/daily-action", response_class=HTMLResponse)
async def admin_daily_action(request: Request) -> Response:
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    return HTMLResponse(_render_admin(get_repo(), get_config()))


@admin_router.post("/daily-action/build")
async def admin_build(request: Request) -> Response:
    """Build any missing drafts for the next week of send days."""
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect

    repo, config = get_repo(), get_config()
    built = 0
    for offset in range(0, 7):
        target = date.today() + timedelta(days=offset)
        if not should_send_on(target, config.daily_action):
            continue
        if get_issue_for_date(repo, target):
            continue
        if build_daily_action(repo, config, target):
            built += 1
    return HTMLResponse(
        _render_admin(repo, config, message=f"Built {built} draft(s).")
    )


@admin_router.post("/daily-action/approve")
async def admin_approve(request: Request, issue_id: int = Form(...)) -> Response:
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    repo, config = get_repo(), get_config()
    set_status(repo, issue_id, "approved")
    return HTMLResponse(_render_admin(repo, config, message="Approved."))


@admin_router.post("/daily-action/regenerate")
async def admin_regenerate(request: Request, action_date: str = Form(...)) -> Response:
    """Rewrite a draft that reads badly. Refuses on anything already sent."""
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    repo, config = get_repo(), get_config()
    target = _parse_date(action_date)
    existing = get_issue_for_date(repo, target)
    if existing and existing["status"] == "sent":
        return HTMLResponse(
            _render_admin(repo, config, error="That action has already been sent.")
        )
    build_daily_action(repo, config, target, force=True)
    return HTMLResponse(_render_admin(repo, config, message="Regenerated."))


@admin_router.post("/daily-action/send")
async def admin_send(request: Request, action_date: str = Form("")) -> Response:
    """Send now, rather than waiting for the scheduler's send hour."""
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    repo, config = get_repo(), get_config()
    target = _parse_date(action_date) if action_date else date.today()
    result = send_daily_action(repo, config, target)
    if result.get("skipped"):
        return HTMLResponse(
            _render_admin(repo, config, error=f"Not sent: {result['skipped']}")
        )
    return HTMLResponse(
        _render_admin(repo, config, message=f"Sent to {result.get('sent', 0)} subscriber(s).")
    )


@admin_router.get("/daily-action/preview/{issue_id}", response_class=HTMLResponse)
async def admin_preview(issue_id: int, request: Request) -> Response:
    redirect = _require_admin(request)
    if redirect is not None:
        return redirect
    repo = get_repo()
    conn = repo._conn()
    try:
        row = conn.execute(
            "SELECT html_content FROM daily_action_issues WHERE id = ?", (issue_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return HTMLResponse("<p>Not found.</p>", status_code=404)
    return HTMLResponse(dict(row)["html_content"])
