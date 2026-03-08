"""Legacy sponsor routes — redirect to /sponsor-blocks."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/")
async def sponsors_redirect():
    return RedirectResponse(url="/sponsor-blocks", status_code=301)


@router.get("/{path:path}")
async def sponsors_catchall(path: str):
    return RedirectResponse(url="/sponsor-blocks", status_code=301)
