"""Scene Graph routes — public knowledge base + admin indexing controls."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader

from weeklyamp.analytics.scene_graph import index_issue
from weeklyamp.web.deps import get_repo, render

logger = logging.getLogger(__name__)

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "web"
_public_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
)

# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

_TYPE_LABELS = {
    "artist": "Artists",
    "venue": "Venues",
    "label": "Labels",
    "producer": "Producers",
    "city": "Cities",
    "event": "Events",
}

_TYPE_ICONS = {
    "artist": "&#127908;",   # microphone
    "venue": "&#127963;",    # stadium
    "label": "&#128191;",    # record
    "producer": "&#127899;", # control knobs
    "city": "&#127961;",     # cityscape
    "event": "&#127914;",    # ticket
}

_REL_LABELS = {
    "mentioned_with": "Mentioned with",
    "performed_at": "Performed at",
    "signed_to": "Signed to",
    "produced_by": "Produced by",
    "based_in": "Based in",
}


@router.get("/scene", response_class=HTMLResponse)
async def scene_index(request: Request):
    """Public Scene Graph landing — search bar + stats + top entities."""
    repo = get_repo()
    stats = repo.get_scene_stats()
    q = request.query_params.get("q", "").strip()
    entity_type = request.query_params.get("type", "").strip() or None
    results = []
    if q:
        results = repo.search_scene_entities(q, entity_type=entity_type, limit=30)

    tpl = _public_env.get_template("scene_index.html")
    return HTMLResponse(tpl.render(
        stats=stats,
        query=q,
        entity_type=entity_type or "",
        results=results,
        type_labels=_TYPE_LABELS,
        type_icons=_TYPE_ICONS,
    ))


@router.get("/scene/search", response_class=HTMLResponse)
async def scene_search(request: Request):
    """Search results page (same template, just with results)."""
    repo = get_repo()
    stats = repo.get_scene_stats()
    q = request.query_params.get("q", "").strip()
    entity_type = request.query_params.get("type", "").strip() or None
    results = repo.search_scene_entities(q, entity_type=entity_type, limit=30) if q else []

    tpl = _public_env.get_template("scene_index.html")
    return HTMLResponse(tpl.render(
        stats=stats,
        query=q,
        entity_type=entity_type or "",
        results=results,
        type_labels=_TYPE_LABELS,
        type_icons=_TYPE_ICONS,
    ))


@router.get("/scene/entity/{slug}", response_class=HTMLResponse)
async def scene_entity_detail(slug: str, request: Request):
    """Entity detail page — bio, connections, mentions timeline."""
    repo = get_repo()
    entity = repo.get_scene_entity_by_slug_any(slug)
    if not entity:
        return HTMLResponse(
            "<h1>Entity not found</h1><p><a href='/scene'>Back to Scene Graph</a></p>",
            status_code=404,
        )
    # Fetch full entity data (connections + mentions)
    full = repo.get_scene_entity(entity["id"])
    if not full:
        return HTMLResponse("<h1>Entity not found</h1>", status_code=404)

    tpl = _public_env.get_template("scene_entity.html")
    return HTMLResponse(tpl.render(
        entity=full,
        type_labels=_TYPE_LABELS,
        type_icons=_TYPE_ICONS,
        rel_labels=_REL_LABELS,
    ))


@router.get("/scene/graph.json")
async def scene_graph_json(request: Request):
    """JSON API: return graph data for JS visualization."""
    repo = get_repo()
    entity_id = request.query_params.get("entity_id")
    if entity_id:
        try:
            entity_id = int(entity_id)
        except (ValueError, TypeError):
            entity_id = None
    limit = 100
    try:
        limit = min(500, int(request.query_params.get("limit", 100)))
    except (ValueError, TypeError):
        pass
    data = repo.get_scene_graph_data(entity_id=entity_id, limit=limit)
    return JSONResponse(data)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@router.get("/admin/scene/", response_class=HTMLResponse)
@router.get("/admin/scene", response_class=HTMLResponse)
async def scene_admin(request: Request):
    """Admin overview — stats, index controls."""
    repo = get_repo()
    stats = repo.get_scene_stats()
    # Get published issues for the index dropdown
    issues = repo.get_published_issues(limit=50)
    return HTMLResponse(render(
        "scene_admin.html",
        stats=stats,
        issues=issues,
        type_labels=_TYPE_LABELS,
        type_icons=_TYPE_ICONS,
        message=request.query_params.get("msg", ""),
    ))


@router.post("/admin/scene/index/{issue_id}")
async def scene_index_issue(issue_id: int, request: Request):
    """Trigger indexing of a specific published issue."""
    repo = get_repo()
    result = index_issue(repo, issue_id)
    msg = f"Indexed issue #{issue_id}: {result.get('entities_found', 0)} entities, {result.get('connections_found', 0)} connections"
    # Check if HTMX request
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'<div class="alert alert-success">{msg}</div>')
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/admin/scene/?msg={msg}", status_code=303)


@router.post("/admin/scene/reindex-all")
async def scene_reindex_all(request: Request):
    """Reindex all published issues."""
    repo = get_repo()
    issues = repo.get_published_issues(limit=500)
    total_entities = 0
    total_connections = 0
    for issue in issues:
        result = index_issue(repo, issue["id"])
        total_entities += result.get("entities_found", 0)
        total_connections += result.get("connections_found", 0)

    msg = f"Reindexed {len(issues)} issues: {total_entities} entities, {total_connections} connections"
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'<div class="alert alert-success">{msg}</div>')
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/admin/scene/?msg={msg}", status_code=303)
