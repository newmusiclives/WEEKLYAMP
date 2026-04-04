"""Advanced analytics routes — NPS, reports, forecasting, media kit."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def analytics_hub(request: Request):
    repo = get_repo()
    config = get_config()
    from weeklyamp.content.analytics_tools import calculate_nps, generate_content_report, forecast_revenue
    nps = calculate_nps(repo)
    content_report = generate_content_report(repo)
    forecasts = forecast_revenue(repo, months=12)
    return HTMLResponse(render("analytics_hub.html",
        nps=nps, content_report=content_report, forecasts=forecasts, config=config))

@router.get("/media-kit", response_class=PlainTextResponse)
async def media_kit_download(request: Request):
    repo = get_repo()
    config = get_config()
    from weeklyamp.content.analytics_tools import generate_media_kit_text
    kit = generate_media_kit_text(repo, config)
    return PlainTextResponse(kit, headers={"Content-Disposition": "attachment; filename=TrueFans_Media_Kit.txt"})
