"""Admin: city-license revenue levers (/admin/license-revenue).

One page to run the levers in ``billing/license_extras.py``: see which are
switched on, preview what each licensee's next invoice would add, and keep
the records the levers bill from (network campaigns, venue listings,
finder's-fee signups, per-licensee options, which city an event belongs to).
The levers themselves are switched on /admin/feature-flags.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from weeklyamp.billing.license_extras import LicenseExtras, bounty_for
from weeklyamp.core.feature_flags import FLAG_METADATA, enabled
from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()

LEVER_CATEGORY = "License revenue"
PRODUCTS = ("amp", "edge", "rise")


def _this_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _clean_month(value: str) -> str:
    value = (value or "").strip()[:7]
    try:
        datetime.strptime(value, "%Y-%m")
        return value
    except ValueError:
        return _this_month()


def _cents(dollars: str) -> int:
    try:
        return int(round(float((dollars or "0").replace("$", "").replace(",", "")) * 100))
    except ValueError:
        return 0


def _back(month: str = "") -> Response:
    # htmx follows HX-Redirect, so every form posts and the page reloads.
    url = "/admin/license-revenue" + (f"?month={month}" if month else "")
    return Response(status_code=204, headers={"HX-Redirect": url})


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def license_revenue_page(request: Request, month: str = ""):
    repo = get_repo()
    config = get_config()
    month = _clean_month(month)

    levers = [
        {"key": k, "label": label, "desc": desc, "on": enabled(k, repo=repo)}
        for k, (label, cat, desc) in FLAG_METADATA.items() if cat == LEVER_CATEGORY
    ]
    licensees = repo.get_licensees()
    by_id = {l["id"]: l for l in licensees}

    engine = LicenseExtras(repo, config)
    preview = []
    for lic in licensees:
        if lic.get("status") in ("cancelled",):
            continue
        rev = next((r for r in repo.get_license_revenue(lic["id"]) if r.get("month") == month), None)
        fee = int(lic.get("license_fee_cents") or 0)
        platform = int(rev.get("platform_share_cents", 0)) if rev else 0
        extras = engine.compute(lic, month, base_platform_cents=fee + platform,
                                sponsor_revenue_cents=int(rev.get("sponsor_revenue_cents", 0)) if rev else 0)
        preview.append({
            "lic": lic, "fee": fee, "platform": platform, "lines": extras.lines,
            "extras": extras.total_cents, "total": fee + platform + extras.total_cents,
        })

    try:
        events = repo._rows("SELECT id, title, event_date, ticket_price_cents, licensee_id, status FROM events ORDER BY id DESC")
    except Exception:
        events = []

    return HTMLResponse(render(
        "license_revenue.html",
        month=month, levers=levers, licensees=licensees, by_id=by_id, preview=preview,
        campaigns=repo.get_network_campaigns(), listings=repo.get_venue_listings(),
        conversions=repo.get_funnel_conversions(month=month), events=events,
        rc=config.license_revenue, products=PRODUCTS,
    ))


@router.post("/options/{licensee_id}")
async def save_options(licensee_id: int, managed_sales: str = Form(""), is_master: str = Form(""),
                       parent_franchise_id: str = Form(""), month: str = Form("")):
    parent = int(parent_franchise_id) if parent_franchise_id.isdigit() and int(parent_franchise_id) != licensee_id else None
    get_repo().set_licensee_revenue_options(
        licensee_id, managed_sales=bool(managed_sales), is_master=bool(is_master), parent_franchise_id=parent)
    return _back(month)


@router.post("/campaigns")
async def add_campaign(sponsor_name: str = Form(...), amount: str = Form("0"), month: str = Form(""),
                       licensee_ids: str = Form("all"), headline: str = Form(""), cta_url: str = Form(""),
                       notes: str = Form("")):
    m = _clean_month(month)
    ids = (licensee_ids or "all").strip()
    if ids != "all":
        ids = ",".join(x.strip() for x in ids.split(",") if x.strip().isdigit()) or "all"
    get_repo().create_network_campaign(sponsor_name.strip(), m, _cents(amount), ids, headline.strip(),
                                       cta_url.strip(), notes.strip())
    return _back(m)


@router.post("/campaigns/{campaign_id}/status")
async def campaign_status(campaign_id: int, status: str = Form(...), month: str = Form("")):
    if status in ("booked", "running", "completed", "cancelled"):
        get_repo().set_network_campaign_status(campaign_id, status)
    return _back(month)


@router.post("/listings")
async def add_listing(licensee_id: int = Form(...), venue_name: str = Form(...), price: str = Form(""),
                      start_month: str = Form(""), contact_email: str = Form(""), notes: str = Form("")):
    config = get_config()
    cents = _cents(price) if (price or "").strip() else config.license_revenue.venue_listing_price_cents
    m = _clean_month(start_month)
    get_repo().create_venue_listing(licensee_id, venue_name.strip(), cents, m, contact_email.strip(), notes.strip())
    return _back(m)


@router.post("/listings/{listing_id}/status")
async def listing_status(listing_id: int, status: str = Form(...), month: str = Form("")):
    if status in ("active", "paused", "cancelled"):
        end = _clean_month(month) if status == "cancelled" else ""
        get_repo().set_venue_listing_status(listing_id, status, end)
    return _back(month)


@router.post("/conversions")
async def add_conversion(licensee_id: int = Form(...), product: str = Form(...), month: str = Form(""),
                         subscriber_email: str = Form("")):
    product = (product or "").lower()
    if product not in PRODUCTS:
        return Response("Unknown product", status_code=400)
    m = _clean_month(month)
    get_repo().create_funnel_conversion(licensee_id, product, m, bounty_for(get_config(), product),
                                        subscriber_email.strip())
    return _back(m)


@router.post("/events/{event_id}")
async def assign_event(event_id: int, licensee_id: str = Form(""), month: str = Form("")):
    repo = get_repo()
    repo._write("UPDATE events SET licensee_id = ? WHERE id = ?",
                (int(licensee_id) if licensee_id.isdigit() else None, event_id))
    return _back(month)
