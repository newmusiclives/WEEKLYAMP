"""Edition-specific public landing pages for targeted subscriber acquisition."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()


@router.get("/for-artists", response_class=HTMLResponse)
async def artists_landing(request: Request):
    repo = get_repo()
    config = get_config()
    subscriber_count = repo.get_subscriber_count()
    return HTMLResponse(render("landing_artists.html", subscriber_count=subscriber_count, config=config))


@router.get("/for-fans", response_class=HTMLResponse)
async def fans_landing(request: Request):
    repo = get_repo()
    config = get_config()
    subscriber_count = repo.get_subscriber_count()
    return HTMLResponse(render("landing_fans.html", subscriber_count=subscriber_count, config=config))


@router.get("/for-industry", response_class=HTMLResponse)
async def industry_landing(request: Request):
    repo = get_repo()
    config = get_config()
    subscriber_count = repo.get_subscriber_count()
    return HTMLResponse(render("landing_industry.html", subscriber_count=subscriber_count, config=config))
