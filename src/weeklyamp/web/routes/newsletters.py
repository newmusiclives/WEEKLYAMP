"""Public newsletters page — edition details with section breakdowns."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from jinja2 import Environment, FileSystemLoader

from weeklyamp.core.config import load_config
from weeklyamp.db.repository import Repository

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent.parent / "templates" / "web"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)

router = APIRouter()


def _get_repo() -> Repository:
    cfg = load_config()
    db_path = cfg.db_path
    if not os.path.isabs(db_path):
        if os.path.exists("/app"):
            db_path = os.path.join("/app", db_path)
        else:
            db_path = os.path.abspath(db_path)
    return Repository(db_path)


@router.get("/newsletters/archive", response_class=HTMLResponse)
async def newsletters_archive():
    repo = _get_repo()
    issues = repo.get_published_issues(limit=50)
    tpl = _env.get_template("archive.html")
    return tpl.render(issues=issues)


@router.get("/newsletters/archive/{issue_number}", response_class=HTMLResponse)
async def newsletter_issue(issue_number: int):
    repo = _get_repo()
    # Find the issue by number
    issues = repo.get_published_issues(limit=100)
    issue = next((i for i in issues if i["issue_number"] == issue_number), None)
    if not issue:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    assembled = repo.get_assembled(issue["id"])
    if not assembled:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    tpl = _env.get_template("archive_issue.html")
    return tpl.render(issue=issue, content=assembled["html_content"])


@router.get("/feed.xml")
async def rss_feed():
    from fastapi.responses import Response
    repo = _get_repo()
    issues = repo.get_published_issues(limit=20)

    items = []
    for issue in issues:
        assembled = repo.get_assembled(issue["id"])
        pub_date = issue.get("publish_date", issue.get("created_at", ""))
        description = assembled["plain_content"][:500] + "..." if assembled and assembled.get("plain_content") else f"Issue #{issue['issue_number']}"
        items.append(
            f"""    <item>
      <title>TrueFans NEWSLETTERS #{issue['issue_number']}{(' — ' + issue['title']) if issue.get('title') else ''}</title>
      <link>https://truefansnewsletters.com/newsletters/archive/{issue['issue_number']}</link>
      <guid>https://truefansnewsletters.com/newsletters/archive/{issue['issue_number']}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{description}]]></description>
    </item>"""
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>TrueFans NEWSLETTERS</title>
    <link>https://truefansnewsletters.com</link>
    <description>The music newsletters for industry professionals, music artists and their fans.</description>
    <language>en-us</language>
    <atom:link href="https://truefansnewsletters.com/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>"""
    return Response(content=xml, media_type="application/xml")


@router.get("/newsletters", response_class=HTMLResponse)
async def newsletters_page():
    repo = _get_repo()
    editions = repo.get_editions(active_only=True)

    # Resolve section_slugs to full section details
    all_sections = repo.get_all_sections()
    sections_map = {s["slug"]: s for s in all_sections}

    editions_with_sections = []
    for ed in editions:
        slugs = [s.strip() for s in ed.get("section_slugs", "").split(",") if s.strip()]
        resolved = [sections_map[s] for s in slugs if s in sections_map]
        editions_with_sections.append({**ed, "sections": resolved})

    tpl = _env.get_template("newsletters.html")
    return tpl.render(editions=editions_with_sections)
