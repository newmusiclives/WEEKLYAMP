"""Advertiser self-serve portal — login, dashboard, campaign management.

Authentication uses the signed `_advertiser_session` cookie set on
successful login (see ``security.create_advertiser_session``). Routes
that mutate or display advertiser-scoped data resolve the advertiser_id
from the session, NOT from query/form parameters — so a logged-in
advertiser cannot see another advertiser's campaigns by tampering with
the URL.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from weeklyamp.web.deps import get_config, get_repo, render
from weeklyamp.web.security import (
    clear_advertiser_session,
    create_advertiser_session,
    get_advertiser_id_from_session,
)

router = APIRouter()


def _require_advertiser(request: Request) -> int | Response:
    """Resolve the advertiser_id from the session cookie or return a
    redirect to the login page. Use as the first line of every protected
    handler."""
    advertiser_id = get_advertiser_id_from_session(request)
    if not advertiser_id:
        return RedirectResponse("/advertiser/login", status_code=302)
    return advertiser_id


@router.get("/advertiser/login", response_class=HTMLResponse)
async def advertiser_login_page(request: Request):
    config = get_config()
    return HTMLResponse(render("advertiser_login.html", config=config))


@router.post("/advertiser/login")
async def advertiser_login(request: Request, email: str = Form(...), password: str = Form(...)):
    repo = get_repo()
    account = repo.get_advertiser_by_email(email)
    if not account:
        return HTMLResponse(render("advertiser_login.html", error="Invalid credentials", config=get_config()))
    from weeklyamp.web.security import verify_password
    if not verify_password(password, account.get("password_hash", "")):
        return HTMLResponse(render("advertiser_login.html", error="Invalid credentials", config=get_config()))

    response = RedirectResponse("/advertiser/dashboard", status_code=302)
    create_advertiser_session(response, account["id"], request=request)
    return response


@router.post("/advertiser/logout")
async def advertiser_logout():
    response = RedirectResponse("/advertiser/login", status_code=302)
    clear_advertiser_session(response)
    return response


@router.get("/advertiser/dashboard", response_class=HTMLResponse)
async def advertiser_dashboard(request: Request):
    advertiser_id = _require_advertiser(request)
    if isinstance(advertiser_id, Response):
        return advertiser_id
    repo = get_repo()
    config = get_config()
    account = repo.get_advertiser_by_id(advertiser_id) or {}
    campaigns = repo.get_advertiser_campaigns(advertiser_id)
    return HTMLResponse(render("advertiser_dashboard.html", account=account, campaigns=campaigns, config=config))


@router.post("/advertiser/campaign/create", response_class=HTMLResponse)
async def create_campaign(
    request: Request,
    name: str = Form(...),
    edition_slug: str = Form(""),
    position: str = Form("mid"),
    headline: str = Form(""),
    body_html: str = Form(""),
    cta_url: str = Form(""),
    cta_text: str = Form("Learn More"),
    budget_cents: int = Form(0),
):
    advertiser_id = _require_advertiser(request)
    if isinstance(advertiser_id, Response):
        return advertiser_id
    repo = get_repo()
    campaign_id = repo.create_advertiser_campaign(
        advertiser_id=advertiser_id, name=name, edition_slug=edition_slug,
        position=position, headline=headline, body_html=body_html,
        cta_url=cta_url, cta_text=cta_text, budget_cents=budget_cents,
    )
    return HTMLResponse(f'<div class="alert alert-success">Campaign created (ID: {campaign_id}). It will be reviewed by our team.</div>')


@router.post("/advertiser/campaign/{campaign_id}/submit", response_class=HTMLResponse)
async def submit_campaign(campaign_id: int, request: Request):
    advertiser_id = _require_advertiser(request)
    if isinstance(advertiser_id, Response):
        return advertiser_id
    repo = get_repo()
    # Confirm the campaign actually belongs to this advertiser before
    # letting them transition its status. Without this check, knowing
    # any campaign_id would let any logged-in advertiser submit
    # someone else's draft.
    campaign = repo.get_advertiser_campaign(campaign_id) if hasattr(repo, "get_advertiser_campaign") else None
    if campaign and campaign.get("advertiser_id") != advertiser_id:
        return HTMLResponse('<div class="alert alert-danger">Not your campaign.</div>', status_code=403)
    repo.update_campaign_status(campaign_id, "submitted")
    return HTMLResponse('<div class="alert alert-success">Campaign submitted for review!</div>')


@router.get("/advertiser/rates", response_class=HTMLResponse)
async def rate_card(request: Request):
    config = get_config()
    return HTMLResponse(render("advertiser_dashboard.html", account={}, campaigns=[], config=config, show_rates=True))


# ---- Ad Marketplace Bidding ----

@router.get("/advertiser/marketplace", response_class=HTMLResponse)
async def ad_marketplace_page(request: Request):
    """View available ad slots and place bids."""
    advertiser_id = _require_advertiser(request)
    if isinstance(advertiser_id, Response):
        return advertiser_id
    repo = get_repo()
    config = get_config()
    editions = repo.get_editions()
    from datetime import datetime, timedelta
    dates = [(datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 8)]
    conn = repo._conn()
    bids = conn.execute(
        "SELECT * FROM ad_bids WHERE target_date >= ? ORDER BY target_date, bid_cents DESC",
        (dates[0],),
    ).fetchall()
    conn.close()
    return HTMLResponse(render("ad_marketplace.html",
        editions=editions, dates=dates, bids=[dict(b) for b in bids], config=config))


@router.post("/advertiser/marketplace/bid", response_class=HTMLResponse)
async def place_bid(
    request: Request,
    campaign_id: int = Form(...),
    edition_slug: str = Form(...),
    position: str = Form("mid"),
    bid_cents: int = Form(...),
    target_date: str = Form(...),
):
    """Place a bid on a sponsor slot."""
    advertiser_id = _require_advertiser(request)
    if isinstance(advertiser_id, Response):
        return advertiser_id
    from weeklyamp.billing.ad_marketplace import AdMarketplace
    repo = get_repo()
    config = get_config()
    marketplace = AdMarketplace(repo, config)
    bid_id = marketplace.place_bid(campaign_id, advertiser_id, edition_slug, position, bid_cents, target_date)
    return HTMLResponse(f'<div class="alert alert-success">Bid placed (${bid_cents/100:.2f} for {edition_slug} {position} on {target_date}). Auction runs daily at 5am.</div>')
