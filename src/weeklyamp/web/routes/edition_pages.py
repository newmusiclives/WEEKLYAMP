"""Edition-specific public landing pages for targeted subscriber acquisition."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
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


@router.get("/license", response_class=HTMLResponse)
async def license_sales(request: Request):
    repo = get_repo()
    config = get_config()
    subscriber_count = repo.get_subscriber_count()
    markets = repo.get_edition_markets()
    # Count city markets
    city_slugs = {"nashville","los-angeles","new-york","atlanta","london","austin","miami","chicago","detroit","memphis","seattle","toronto","berlin","lagos","tokyo","seoul","paris","sao-paulo","mumbai","kingston"}
    cities = [m for m in markets if m.get("market_slug") in city_slugs]
    return HTMLResponse(render("sales_license.html", subscriber_count=subscriber_count, cities=cities, config=config))


@router.post("/license/apply", response_class=HTMLResponse)
async def license_apply(request: Request, company_name: str = Form(...), contact_name: str = Form(...), email: str = Form(...), phone: str = Form(""), city: str = Form(""), message: str = Form("")):
    repo = get_repo()
    from weeklyamp.web.security import hash_password
    temp_password = "pending"
    pw_hash = hash_password(temp_password)
    repo.create_licensee(company_name, contact_name, email, pw_hash, city_market_slug=city, edition_slugs="fan,artist,industry", license_fee_cents=9900, revenue_share_pct=20.0)
    return HTMLResponse('<div style="padding:40px;text-align:center;"><h2 style="color:#10b981;">Application Received!</h2><p style="color:#9ca3af;font-size:18px;">We\'ll review your application and get back to you within 48 hours.</p></div>')
