"""Event management — virtual and in-person music events."""
from __future__ import annotations
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def events_page(request: Request):
    repo = get_repo()
    conn = repo._conn()
    events = conn.execute("SELECT * FROM events ORDER BY event_date DESC LIMIT 20").fetchall()
    conn.close()
    return HTMLResponse(render("events.html", events=[dict(e) for e in events]))

@router.post("/create", response_class=HTMLResponse)
async def create_event(request: Request, title: str = Form(...), description: str = Form(""), event_type: str = Form("virtual"), edition_slug: str = Form(""), location: str = Form(""), event_date: str = Form(""), ticket_price_cents: int = Form(0), max_attendees: int = Form(0)):
    repo = get_repo()
    conn = repo._conn()
    conn.execute(
        "INSERT INTO events (title, description, event_type, edition_slug, location, event_date, ticket_price_cents, max_attendees, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft')",
        (title, description, event_type, edition_slug, location, event_date, ticket_price_cents, max_attendees),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(f'<div class="alert alert-success">Event "{title}" created.</div>')

@router.get("/public", response_class=HTMLResponse)
async def public_events(request: Request):
    repo = get_repo()
    conn = repo._conn()
    events = conn.execute("SELECT * FROM events WHERE status = 'published' ORDER BY event_date ASC").fetchall()
    conn.close()
    return HTMLResponse(render("events_public.html", events=[dict(e) for e in events]))

@router.post("/register/{event_id}", response_class=HTMLResponse)
async def register_event(event_id: int, request: Request, email: str = Form(...), name: str = Form("")):
    repo = get_repo()
    conn = repo._conn()
    try:
        conn.execute("INSERT INTO event_registrations (event_id, email, name) VALUES (?, ?, ?)", (event_id, email, name))
        conn.execute("UPDATE events SET registered_count = registered_count + 1 WHERE id = ?", (event_id,))
        conn.commit()
    except Exception:
        conn.close()
        return HTMLResponse('<div class="alert alert-warning">Already registered.</div>')
    conn.close()
    return HTMLResponse('<div class="alert alert-success">You\'re registered! Check your email for details.</div>')
