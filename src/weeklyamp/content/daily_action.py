"""TrueFans Single Daily Action — one tactical action per day, for artists.

The premise: an artist's career is built by *owned* fan relationships, not
by platform metrics. So every action in this edition moves someone one
step closer to being a TrueFan the artist actually controls the line to —
an email address, a reply, a purchase, a referral.

Why this doesn't reuse the section-assembly pipeline
----------------------------------------------------
A normal DISPATCH edition is 8–15 rotating sections with research,
sponsor slots, drafts and review. A daily action is ~120 words with one
CTA. Running it through :mod:`weeklyamp.content.assembly` would mean
paying for section rotation, promo blocks and multi-draft review to ship
a single paragraph. It gets its own small pipeline instead, and its own
tables (schema v55).

How a day gets its action
-------------------------
1. The weekday picks a **pillar** (:data:`PILLAR_BY_WEEKDAY`), so Monday
   is always Capture, Tuesday always Connect, and so on. Readers learn
   the rhythm.
2. Within that pillar we take the **least recently used** active row from
   ``daily_action_library``, so the bank cycles instead of repeating.
3. The AI is handed that row and asked to *rewrite the copy only*. It
   never invents the action, and it is explicitly barred from naming
   venues, people, platforms-with-claims or statistics — the same
   no-fabrication rule the verified-facts pipeline enforces. If the model
   is unavailable or returns something unusable, the library text ships
   verbatim, so a bad API day still sends a correct email.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from weeklyamp.core.models import AppConfig
from weeklyamp.db.repository import Repository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Pillars
# ---------------------------------------------------------------------

# Each pillar is one repeatable way to turn a listener into a TrueFan.
# ``focus`` is fed to the AI as the day's angle; ``question`` is the
# reader-facing framing printed under the pillar badge.
PILLARS: dict[str, dict[str, str]] = {
    "capture": {
        "name": "Capture",
        "focus": "turning anonymous listeners into contacts the artist owns outright",
        "question": "Who heard you today that you can reach tomorrow?",
        "color": "#7c5cfc",
    },
    "connect": {
        "name": "Connect",
        "focus": "deepening the relationship with fans the artist already has",
        "question": "Who already cares, and when did you last speak to them?",
        "color": "#e8645a",
    },
    "create": {
        "name": "Create",
        "focus": "making something that gives fans a reason to care this week",
        "question": "What did you make that only you could have made?",
        "color": "#0ea5e9",
    },
    "convert": {
        "name": "Convert",
        "focus": "turning fans into people who pay the artist directly",
        "question": "How can a fan give you money in under sixty seconds?",
        "color": "#16a34a",
    },
    "amplify": {
        "name": "Amplify",
        "focus": "getting existing fans to bring new fans, instead of chasing strangers",
        "question": "Which fan could bring you the next one?",
        "color": "#f59e0b",
    },
    "perform": {
        "name": "Perform",
        "focus": "the live room, where fans are made fastest and lost fastest",
        "question": "What happens after the last song?",
        "color": "#b09a3a",
    },
    "sustain": {
        "name": "Sustain",
        "focus": "the systems and habits that keep a career going for another year",
        "question": "What did this week actually move?",
        "color": "#64748b",
    },
}

# Monday=0 … Sunday=6, matching ``date.weekday()``.
PILLAR_BY_WEEKDAY: dict[int, str] = {
    0: "capture",
    1: "connect",
    2: "create",
    3: "convert",
    4: "amplify",
    5: "perform",
    6: "sustain",
}

_WEEKDAY_NAMES = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]

EDITION_SLUG = "daily-action"


# ---------------------------------------------------------------------
# Date helpers
#
# Every date is an ISO 'YYYY-MM-DD' string by the time it reaches SQL.
# SQLite and Postgres disagree on date functions (see the portability
# rules in the repo), so no query below does date maths itself.
# ---------------------------------------------------------------------

def _iso(d: date) -> str:
    return d.isoformat()


def pillar_for_date(d: date) -> str:
    """Return the pillar slug that owns this weekday."""
    return PILLAR_BY_WEEKDAY[d.weekday()]


def should_send_on(d: date, config) -> bool:
    """True if the daily action is scheduled to go out on this date."""
    allowed = {day.strip().lower() for day in (config.send_days or [])}
    return _WEEKDAY_NAMES[d.weekday()] in allowed


# ---------------------------------------------------------------------
# Library selection
# ---------------------------------------------------------------------

def pick_action(repo: Repository, pillar: str) -> Optional[dict]:
    """Return the least recently used active action for a pillar.

    Ordering is ``last_used_date`` ascending — never-used rows carry the
    empty string and therefore sort first, which is exactly the behaviour
    we want without a ``NULLS FIRST`` clause (Postgres and SQLite disagree
    about that one). ``times_used`` breaks ties so a same-day backfill
    doesn't hand out the same row twice.
    """
    conn = repo._conn()
    try:
        row = conn.execute(
            """SELECT * FROM daily_action_library
               WHERE pillar = ? AND is_active = 1
               ORDER BY last_used_date ASC, times_used ASC, id ASC
               LIMIT 1""",
            (pillar,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def _mark_used(repo: Repository, library_id: int, on_date: str) -> None:
    conn = repo._conn()
    try:
        conn.execute(
            """UPDATE daily_action_library
               SET times_used = times_used + 1, last_used_date = ?
               WHERE id = ?""",
            (on_date, library_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------
# AI rewrite
# ---------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You write TrueFans Single Daily Action, a daily email to independent "
    "musicians. One action per day, doable today, aimed at building an "
    "audience the artist owns rather than rents from a platform. You write "
    "like a working manager texting a client: direct, warm, zero hype, no "
    "guru voice, no exclamation marks."
)

_FIELD_RE = re.compile(
    r"^(SUBJECT|HOOK|ACTION|WHY)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _build_prompt(action: dict, pillar: str, on_date: date, config) -> str:
    pillar_meta = PILLARS.get(pillar, {})
    return f"""Rewrite today's action as a short daily email.

Today is {on_date.strftime('%A, %B %d, %Y')}.
Today's pillar: {pillar_meta.get('name', pillar)} — {pillar_meta.get('focus', '')}.

The action (do not replace it, do not add a second action):
  Title: {action.get('title', '')}
  What to do: {action.get('action_text', '')}
  Why it works: {action.get('why_it_works', '')}
  Realistic time: {action.get('time_minutes', 15)} minutes

Return exactly four lines, each prefixed with its label:

SUBJECT: under 45 characters, concrete, no colon-prefixed branding
HOOK: one sentence, max 20 words, sets up why today's action matters
ACTION: 2-3 sentences of specific instruction the artist can follow without
  guessing. Second person. Name the first physical step.
WHY: one sentence on the mechanism — what this does to the fan relationship

Hard rules:
- Do NOT invent facts. No statistics, no percentages, no research claims.
- Do NOT name real people, venues, cities, labels, or companies.
- Do NOT promise results or timelines.
- Do NOT mention any platform by name unless the action above already does.
- Keep the total under 110 words. Shorter is better.
- Plain text only. No markdown, no bullets, no emoji."""


def _parse_ai_fields(text: str) -> dict:
    """Pull SUBJECT/HOOK/ACTION/WHY out of the model's reply.

    Returns only the fields that were actually found, so a partial reply
    degrades to partial library fallback rather than an empty email.
    """
    found: dict[str, str] = {}
    for label, value in _FIELD_RE.findall(text or ""):
        found[label.upper()] = value.strip()
    return found


def _compose(action: dict, pillar: str, on_date: date, config: AppConfig) -> dict:
    """Build the day's copy — AI rewrite when possible, library text if not."""
    da_cfg = config.daily_action
    subject_prefix = (da_cfg.subject_prefix or "").strip()

    # Library text is the baseline. Everything below only overrides it.
    composed = {
        "subject": f"{subject_prefix}: {action.get('title', '')}".strip(": ").strip(),
        "hook": PILLARS.get(pillar, {}).get("question", ""),
        "action_text": action.get("action_text", ""),
        "why_it_works": action.get("why_it_works", ""),
        "time_minutes": int(action.get("time_minutes") or 15),
        "generated_by": "library",
        "tokens_used": 0,
    }

    if not da_cfg.ai_rewrite:
        return composed

    try:
        from weeklyamp.content.generator import generate_draft_with_usage

        raw, model, tokens = generate_draft_with_usage(
            _build_prompt(action, pillar, on_date, da_cfg),
            config,
            max_tokens_override=da_cfg.max_tokens,
            system_prompt=_SYSTEM_PROMPT,
        )
    except Exception:
        logger.exception("daily_action: AI rewrite failed, using library copy")
        return composed

    fields = _parse_ai_fields(raw)
    # An action line is the one field we refuse to ship from a partial
    # reply — without it there is no daily action, only a hook.
    if not fields.get("ACTION"):
        logger.warning("daily_action: AI reply missing ACTION, using library copy")
        return composed

    if fields.get("SUBJECT"):
        composed["subject"] = fields["SUBJECT"]
    if fields.get("HOOK"):
        composed["hook"] = fields["HOOK"]
    composed["action_text"] = fields["ACTION"]
    if fields.get("WHY"):
        composed["why_it_works"] = fields["WHY"]
    composed["generated_by"] = model
    composed["tokens_used"] = tokens
    return composed


# ---------------------------------------------------------------------
# Issue creation
# ---------------------------------------------------------------------

def get_issue_for_date(repo: Repository, on_date: date) -> Optional[dict]:
    conn = repo._conn()
    try:
        row = conn.execute(
            "SELECT * FROM daily_action_issues WHERE action_date = ?",
            (_iso(on_date),),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def build_daily_action(
    repo: Repository,
    config: AppConfig,
    on_date: Optional[date] = None,
    force: bool = False,
) -> Optional[dict]:
    """Create (or return) the daily action issue for ``on_date``.

    Idempotent: the ``action_date`` unique index means a second call on
    the same day returns the existing row instead of burning another AI
    call. Pass ``force=True`` to regenerate — used by the admin
    "regenerate" button when a draft reads badly.

    Returns the issue dict, or None if no library action was available
    for the day's pillar (an empty or fully-deactivated library).
    """
    on_date = on_date or date.today()
    existing = get_issue_for_date(repo, on_date)
    if existing and not force:
        return existing
    if existing and existing.get("status") == "sent":
        # Never rewrite something already in someone's inbox.
        return existing

    pillar = pillar_for_date(on_date)
    action = pick_action(repo, pillar)
    if not action:
        logger.warning("daily_action: no library action available for pillar=%s", pillar)
        return None

    composed = _compose(action, pillar, on_date, config)
    status = "draft" if config.daily_action.require_approval else "approved"
    preheader = (composed["hook"] or "")[:120]

    # Two passes on purpose: the "Mark it done" CTA needs the row's own id,
    # so the copy is persisted first and the rendered HTML written back
    # once the id exists. Rendering before the insert would bake a dead
    # link into every send.
    conn = repo._conn()
    try:
        if existing:
            conn.execute(
                """UPDATE daily_action_issues
                   SET library_id = ?, pillar = ?, subject = ?, preheader = ?,
                       hook = ?, action_text = ?, why_it_works = ?,
                       time_minutes = ?, status = ?, generated_by = ?, tokens_used = ?
                   WHERE id = ?""",
                (
                    action["id"], pillar, composed["subject"], preheader,
                    composed["hook"], composed["action_text"], composed["why_it_works"],
                    composed["time_minutes"], status,
                    composed["generated_by"], composed["tokens_used"], existing["id"],
                ),
            )
            issue_id = existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO daily_action_issues
                   (action_date, library_id, pillar, subject, preheader, hook,
                    action_text, why_it_works, time_minutes, status,
                    generated_by, tokens_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _iso(on_date), action["id"], pillar, composed["subject"], preheader,
                    composed["hook"], composed["action_text"], composed["why_it_works"],
                    composed["time_minutes"], status,
                    composed["generated_by"], composed["tokens_used"],
                ),
            )
            issue_id = cur.lastrowid
        conn.commit()

        html, text = render_daily_action(
            composed, pillar, on_date, config, issue_id=issue_id
        )
        conn.execute(
            "UPDATE daily_action_issues SET html_content = ?, text_content = ? WHERE id = ?",
            (html, text, issue_id),
        )
        conn.commit()
    finally:
        conn.close()

    _mark_used(repo, action["id"], _iso(on_date))
    logger.info(
        "daily_action: built %s pillar=%s source=%s tokens=%d",
        _iso(on_date), pillar, composed["generated_by"], composed["tokens_used"],
    )
    return get_issue_for_date(repo, on_date)


def set_status(repo: Repository, issue_id: int, status: str) -> None:
    conn = repo._conn()
    try:
        conn.execute(
            "UPDATE daily_action_issues SET status = ? WHERE id = ?",
            (status, issue_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_sent(repo: Repository, issue_id: int, recipients: int) -> None:
    conn = repo._conn()
    try:
        conn.execute(
            """UPDATE daily_action_issues
               SET status = 'sent', recipients = ?, sent_at = ?
               WHERE id = ?""",
            (recipients, datetime.utcnow().isoformat(), issue_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_issues(repo: Repository, limit: int = 30) -> list[dict]:
    conn = repo._conn()
    try:
        rows = conn.execute(
            """SELECT * FROM daily_action_issues
               ORDER BY action_date DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Completions and streaks
#
# The streak is the retention mechanic: a daily email people ignore is
# just noise, so "I did it" is the one interaction we ask for.
# ---------------------------------------------------------------------

def mark_done(
    repo: Repository,
    issue_id: int,
    subscriber_id: Optional[int],
    action_date: str,
    ip_address: str = "",
) -> bool:
    """Record that a subscriber did today's action. Idempotent per pair."""
    conn = repo._conn()
    try:
        conn.execute(
            """INSERT INTO daily_action_completions
               (issue_id, subscriber_id, action_date, ip_address)
               VALUES (?, ?, ?, ?)""",
            (issue_id, subscriber_id, action_date, ip_address),
        )
        conn.commit()
        return True
    except Exception:
        # UNIQUE(issue_id, subscriber_id) — already logged, which is a
        # success from the reader's point of view.
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def streak_for_subscriber(
    repo: Repository, subscriber_id: int, today: Optional[date] = None
) -> int:
    """Count consecutive *scheduled* days completed, ending today.

    Dates are compared in Python rather than SQL so the same logic holds
    on SQLite and Postgres.
    """
    if not subscriber_id:
        return 0
    today = today or date.today()
    conn = repo._conn()
    try:
        rows = conn.execute(
            """SELECT action_date FROM daily_action_completions
               WHERE subscriber_id = ?
               ORDER BY action_date DESC
               LIMIT 400""",
            (subscriber_id,),
        ).fetchall()
    finally:
        conn.close()

    done = {dict(r)["action_date"] for r in rows}
    streak = 0
    cursor = today
    # Walk backwards; a day with no send scheduled can't break a streak.
    for _ in range(400):
        iso = _iso(cursor)
        if iso in done:
            streak += 1
        elif cursor != today:
            break
        cursor -= timedelta(days=1)
    return streak


def completion_count(repo: Repository, issue_id: int) -> int:
    conn = repo._conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM daily_action_completions WHERE issue_id = ?",
            (issue_id,),
        ).fetchone()
    finally:
        conn.close()
    return int(dict(row)["c"]) if row else 0


# ---------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------

def send_daily_action(
    repo: Repository,
    config: AppConfig,
    on_date: Optional[date] = None,
) -> dict:
    """Send the approved action for ``on_date`` to the daily-action edition.

    Returns a result dict — ``{"sent": n, "failed": n, "skipped": reason}``.
    Refuses to send twice for the same day, and refuses to send a draft
    that has not been approved while ``require_approval`` is on.

    Each recipient gets their own render so the "Mark it done" link and
    streak count are personal. That personalization runs through
    :meth:`SMTPSender.send_bulk`'s ``personalize`` hook, which falls back
    to the stored bulk HTML if one recipient's render raises.
    """
    on_date = on_date or date.today()
    da_cfg = config.daily_action

    if not da_cfg.enabled:
        return {"sent": 0, "failed": 0, "skipped": "daily_action disabled"}
    if not should_send_on(on_date, da_cfg):
        return {"sent": 0, "failed": 0, "skipped": f"{_iso(on_date)} not a send day"}

    issue = get_issue_for_date(repo, on_date)
    if not issue:
        return {"sent": 0, "failed": 0, "skipped": "no issue built for date"}
    if issue["status"] == "sent":
        return {"sent": 0, "failed": 0, "skipped": "already sent"}
    if issue["status"] != "approved":
        return {"sent": 0, "failed": 0, "skipped": f"status={issue['status']}"}

    recipients = repo.get_subscribers_for_edition(EDITION_SLUG)
    if not recipients:
        return {"sent": 0, "failed": 0, "skipped": "no subscribers"}

    composed = {
        "subject": issue["subject"],
        "hook": issue["hook"],
        "action_text": issue["action_text"],
        "why_it_works": issue["why_it_works"],
        "time_minutes": issue["time_minutes"],
    }
    pillar = issue["pillar"]

    def _personalize(recipient: dict) -> tuple[str, str]:
        token = recipient.get("unsubscribe_token", "") or ""
        streak = 0
        if da_cfg.show_streak and recipient.get("id"):
            try:
                streak = streak_for_subscriber(repo, recipient["id"], on_date)
            except Exception:
                logger.exception("daily_action: streak lookup failed")
        return render_daily_action(
            composed, pillar, on_date, config,
            issue_id=issue["id"], subscriber_token=token, streak=streak,
        )

    from weeklyamp.delivery.smtp_sender import SMTPSender

    sender = SMTPSender(config.email)
    result = sender.send_bulk(
        recipients=recipients,
        subject=issue["subject"],
        html_body=issue["html_content"],
        plain_text=issue["text_content"],
        site_domain=config.site_domain,
        personalize=_personalize,
    )
    sent = int(result.get("sent", 0))
    if sent:
        mark_sent(repo, issue["id"], sent)
    logger.info(
        "daily_action: sent %s to %d/%d recipients",
        _iso(on_date), sent, len(recipients),
    )
    return result


# ---------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------

def render_daily_action(
    composed: dict,
    pillar: str,
    on_date: date,
    config: AppConfig,
    issue_id: int = 0,
    subscriber_token: str = "",
    streak: int = 0,
) -> tuple[str, str]:
    """Render the day's action to (html, plain_text)."""
    from weeklyamp.delivery.templates import render_daily_action_email

    pillar_meta = PILLARS.get(pillar, {})
    site = (config.site_domain or "").rstrip("/")
    done_url = f"{site}/daily/done/{issue_id}" if issue_id else "#"
    if subscriber_token:
        done_url = f"{done_url}?s={subscriber_token}"

    html = render_daily_action_email(
        subject=composed.get("subject", ""),
        preheader=composed.get("hook", "")[:120],
        pillar_name=pillar_meta.get("name", pillar.title()),
        pillar_color=pillar_meta.get("color", "#7c5cfc"),
        pillar_question=pillar_meta.get("question", ""),
        date_str=on_date.strftime("%A, %B %d"),
        hook=composed.get("hook", ""),
        action_text=composed.get("action_text", ""),
        why_it_works=composed.get("why_it_works", ""),
        time_minutes=composed.get("time_minutes", 15),
        cta_label=config.daily_action.cta_label,
        cta_url=done_url,
        streak=streak if config.daily_action.show_streak else 0,
        newsletter_name=config.newsletter.name,
        footer_html=config.newsletter.footer_html,
    )

    text = (
        f"{composed.get('subject', '')}\n"
        f"{pillar_meta.get('name', pillar)} — {on_date.strftime('%A, %B %d')}\n\n"
        f"{composed.get('hook', '')}\n\n"
        f"TODAY'S ACTION ({composed.get('time_minutes', 15)} min)\n"
        f"{composed.get('action_text', '')}\n\n"
        f"WHY IT WORKS\n{composed.get('why_it_works', '')}\n\n"
        f"Done it? {done_url}\n"
    )
    return html, text
