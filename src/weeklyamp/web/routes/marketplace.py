"""Creator marketplace — connect artists with collaborators and services."""
from __future__ import annotations
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()

LISTING_TYPES = [("service", "Service"), ("collaboration", "Collaboration"), ("job", "Job"), ("gear", "Gear")]

@router.get("/", response_class=HTMLResponse)
async def marketplace_page(request: Request):
    repo = get_repo()
    conn = repo._conn()
    listings = conn.execute("SELECT * FROM creator_marketplace WHERE status = 'active' ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return HTMLResponse(render("marketplace.html", listings=[dict(l) for l in listings], listing_types=LISTING_TYPES))

@router.post("/create", response_class=HTMLResponse)
async def create_listing(request: Request, listing_type: str = Form(...), title: str = Form(...), description: str = Form(""), poster_email: str = Form(""), poster_name: str = Form(""), category: str = Form(""), price_range: str = Form(""), location: str = Form("")):
    repo = get_repo()
    conn = repo._conn()
    conn.execute(
        "INSERT INTO creator_marketplace (listing_type, title, description, poster_email, poster_name, category, price_range, location) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (listing_type, title, description, poster_email, poster_name, category, price_range, location),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(f'<div class="alert alert-success">Listing "{title}" posted!</div>')
