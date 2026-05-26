"""Living Editions — web-hosted versions of published newsletter issues.

Public routes let anyone read the living web version. Admin routes let
the editor update the web HTML after sending, turning the emailed
snapshot into a continuously-updated web page.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from jinja2 import Environment, FileSystemLoader

from weeklyamp.core.config import load_config
from weeklyamp.web.deps import get_repo, render

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent.parent / "templates" / "web"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)

router = APIRouter()


# ---------------------------------------------------------------------------
# Public: view a living edition
# ---------------------------------------------------------------------------

@router.get("/edition/{issue_id}", response_class=HTMLResponse)
async def view_edition(issue_id: int):
    """Public page showing the living web version of a published issue."""
    repo = get_repo()
    cfg = load_config()

    # Look up the assembled issue — we accept assembled_issues.id directly
    assembled = repo.get_assembled_by_id(issue_id)
    if not assembled:
        # Fall back: maybe issue_id is the issues.id foreign key
        assembled = repo.get_assembled(issue_id)
    if not assembled:
        return HTMLResponse(
            _env.get_template("404.html").render(),
            status_code=404,
        )

    # Get the parent issue for metadata
    issue = None
    try:
        conn = repo._conn()
        row = conn.execute(
            "SELECT * FROM issues WHERE id = ?",
            (assembled["issue_id"],),
        ).fetchone()
        conn.close()
        issue = dict(row) if row else None
    except Exception:
        pass

    issue_number = issue.get("issue_number", "?") if issue else "?"
    issue_title = issue.get("title", "") if issue else ""
    edition_slug = issue.get("edition_slug", "") if issue else ""

    # Use web_html if available, fall back to html_content
    web_html = assembled.get("web_html", "") or assembled.get("html_content", "")
    web_updates_count = assembled.get("web_updates_count", 0) or 0
    last_web_update = assembled.get("last_web_update", "") or ""
    published_at = assembled.get("published_at", "") or ""

    tpl = _env.get_template("live_edition.html")
    return HTMLResponse(tpl.render(
        web_html=web_html,
        issue_number=issue_number,
        issue_title=issue_title,
        edition_slug=edition_slug,
        web_updates_count=web_updates_count,
        last_web_update=last_web_update,
        published_at=published_at,
        assembled_id=assembled["id"],
        site_domain=cfg.site_domain.rstrip("/"),
        plausible_domain=cfg.analytics.plausible_domain,
        newsletter_name=cfg.newsletter.name,
    ))


# ---------------------------------------------------------------------------
# Admin: edit the living web version
# ---------------------------------------------------------------------------

@router.get("/admin/editions/{issue_id}/live", response_class=HTMLResponse)
async def edit_live_edition(issue_id: int):
    """Admin form for editing the web version of a published issue."""
    repo = get_repo()

    assembled = repo.get_assembled_by_id(issue_id)
    if not assembled:
        assembled = repo.get_assembled(issue_id)
    if not assembled:
        return HTMLResponse(render("404.html"), status_code=404)

    # Get the parent issue for context
    issue = None
    try:
        conn = repo._conn()
        row = conn.execute(
            "SELECT * FROM issues WHERE id = ?",
            (assembled["issue_id"],),
        ).fetchone()
        conn.close()
        issue = dict(row) if row else None
    except Exception:
        pass

    issue_number = issue.get("issue_number", "?") if issue else "?"
    issue_title = issue.get("title", "") if issue else ""

    web_html = assembled.get("web_html", "") or assembled.get("html_content", "")
    html_content = assembled.get("html_content", "")
    web_updates_count = assembled.get("web_updates_count", 0) or 0
    has_diverged = web_html != html_content

    return HTMLResponse(render(
        "edit_live_edition.html",
        assembled=assembled,
        issue_number=issue_number,
        issue_title=issue_title,
        web_html=web_html,
        html_content=html_content,
        web_updates_count=web_updates_count,
        has_diverged=has_diverged,
        assembled_id=assembled["id"],
    ))


@router.post("/admin/editions/{issue_id}/live", response_class=HTMLResponse)
async def save_live_edition(issue_id: int, web_html: str = Form(...)):
    """Save an updated web version of the newsletter issue."""
    repo = get_repo()

    assembled = repo.get_assembled_by_id(issue_id)
    if not assembled:
        assembled = repo.get_assembled(issue_id)
    if not assembled:
        return HTMLResponse(render("404.html"), status_code=404)

    repo.update_web_html(assembled["id"], web_html)

    # Redirect back to the edit form with a success indicator
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        f"/admin/editions/{assembled['id']}/live?saved=1",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Admin: list all published editions with links
# ---------------------------------------------------------------------------

@router.get("/admin/editions", response_class=HTMLResponse)
async def list_editions():
    """Admin list of all published issues with living edition links."""
    repo = get_repo()
    editions = repo.get_published_editions()
    return HTMLResponse(render(
        "admin_live_editions.html",
        editions=editions,
    ))
