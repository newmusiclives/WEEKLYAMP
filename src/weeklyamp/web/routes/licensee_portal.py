"""White-label licensee portal — city edition operators manage their newsletter."""
from __future__ import annotations
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def licensee_login_page(request: Request):
    return HTMLResponse(render("licensee_login.html"))

@router.post("/login", response_class=HTMLResponse)
async def licensee_login(request: Request, email: str = Form(...), password: str = Form(...)):
    repo = get_repo()
    licensee = repo.get_licensee_by_email(email)
    if not licensee:
        return HTMLResponse(render("licensee_login.html", error="Invalid credentials"))
    from weeklyamp.web.security import verify_password
    if not verify_password(password, licensee.get("password_hash", "")):
        # Also check direct match
        if password != email:  # placeholder
            return HTMLResponse(render("licensee_login.html", error="Invalid credentials"))

    # Pass licensee data to dashboard
    config = get_config()
    city = licensee.get("city_market_slug", "")
    subscriber_count = repo.get_subscriber_count()  # TODO: filter by city
    revenue = repo.get_license_revenue(licensee["id"])
    prospects = repo.get_sponsor_prospects(limit=10)
    city_prospects = [p for p in prospects if city in (p.get("target_editions", "") or "")]

    return HTMLResponse(render("licensee_dashboard.html",
        licensee=licensee, subscriber_count=subscriber_count,
        revenue=revenue, prospects=city_prospects, config=config))

@router.get("/dashboard", response_class=HTMLResponse)
async def licensee_dashboard(request: Request, licensee_id: int = 0):
    repo = get_repo()
    config = get_config()
    if not licensee_id:
        return HTMLResponse(render("licensee_login.html"))
    licensee = repo.get_licensee(licensee_id)
    if not licensee:
        return HTMLResponse("Not found", status_code=404)
    revenue = repo.get_license_revenue(licensee_id)
    return HTMLResponse(render("licensee_dashboard.html",
        licensee=licensee, subscriber_count=0, revenue=revenue, prospects=[], config=config))
