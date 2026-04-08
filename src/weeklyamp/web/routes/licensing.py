"""Licensing management — city edition franchise administration with Manifest billing."""
from __future__ import annotations

import socket

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()


@router.post("/{licensee_id}/branding")
async def update_licensee_branding(
    licensee_id: int,
    request: Request,
    custom_domain: str = Form(""),
    logo_url: str = Form(""),
    primary_color: str = Form(""),
    footer_html: str = Form(""),
    sender_name: str = Form(""),
    reply_to_email: str = Form(""),
):
    """Update branding fields for a licensee. Setting a new custom_domain
    automatically clears the verified flag and generates a fresh DNS
    verification token.
    """
    repo = get_repo()
    repo.update_licensee_branding(
        licensee_id,
        custom_domain=custom_domain or None,
        logo_url=logo_url or None,
        primary_color=primary_color or None,
        footer_html=footer_html or None,
        sender_name=sender_name or None,
        reply_to_email=reply_to_email or None,
    )
    repo.log_admin_action(
        action="licensee.branding.update",
        target_type="licensee",
        target_id=str(licensee_id),
        ip_address=request.client.host if request.client else "",
    )
    return RedirectResponse(f"/admin/licensing/{licensee_id}", status_code=303)


@router.post("/{licensee_id}/verify-domain")
async def verify_licensee_domain(licensee_id: int, request: Request):
    """Verify ownership of a licensee's custom domain via DNS TXT record.

    Looks up `_truefans-verify.<domain>` and checks for a TXT record
    matching the stored verify token. Returns JSON with verified status.
    Idempotent — safe to call repeatedly.
    """
    repo = get_repo()
    lic = repo.get_licensee(licensee_id)
    if not lic:
        return JSONResponse({"error": "licensee not found"}, status_code=404)

    domain = (lic.get("custom_domain") or "").strip()
    expected_token = (lic.get("domain_verify_token") or "").strip()
    if not domain or not expected_token:
        return JSONResponse({
            "verified": False,
            "error": "no custom_domain or verify_token set",
        }, status_code=400)

    record_name = f"_truefans-verify.{domain}"
    found_records: list[str] = []
    verified = False

    # Best-effort DNS TXT lookup. Try dnspython if available, fall back
    # to a stub that just reports "lookup unavailable".
    try:
        import dns.resolver  # type: ignore
        try:
            answers = dns.resolver.resolve(record_name, "TXT", lifetime=5)
            for r in answers:
                # Strings come as a list of byte segments per record
                txt = "".join(
                    s.decode() if isinstance(s, bytes) else str(s) for s in r.strings
                )
                found_records.append(txt)
                if txt.strip() == expected_token:
                    verified = True
        except Exception as exc:
            return JSONResponse({
                "verified": False,
                "domain": domain,
                "expected_record": record_name,
                "expected_value": expected_token,
                "error": f"DNS lookup failed: {type(exc).__name__}",
            })
    except ImportError:
        return JSONResponse({
            "verified": False,
            "domain": domain,
            "expected_record": record_name,
            "expected_value": expected_token,
            "error": "dnspython not installed — cannot verify automatically",
        }, status_code=503)

    if verified:
        repo.mark_licensee_domain_verified(licensee_id)
        repo.log_admin_action(
            action="licensee.domain.verified",
            target_type="licensee",
            target_id=str(licensee_id),
            detail=domain,
            ip_address=request.client.host if request.client else "",
        )
        # Tell the running domain router to rebuild its cache so the
        # new tenant becomes routable immediately.
        try:
            for mw in request.app.user_middleware:
                if mw.cls.__name__ == "DomainRoutingMiddleware":
                    # The middleware instance is constructed lazily; we
                    # can't reach it here without app.middleware_stack
                    # introspection. Skipping — the next request will
                    # rebuild the cache when its TTL expires anyway.
                    pass
        except Exception:
            pass

    return JSONResponse({
        "verified": verified,
        "domain": domain,
        "expected_record": record_name,
        "expected_value": expected_token,
        "found_records": found_records,
    })

@router.get("/", response_class=HTMLResponse)
async def licensing_page(request: Request):
    repo = get_repo()
    config = get_config()
    licensees = repo.get_licensees()
    markets = repo.get_edition_markets()
    invoices = repo.get_invoices(entity_type="licensee") if config.paid_tiers.enabled else []
    return HTMLResponse(render("licensing.html", licensees=licensees, markets=markets, invoices=invoices, config=config))

@router.get("/{licensee_id}", response_class=HTMLResponse)
async def licensee_detail(licensee_id: int, request: Request):
    repo = get_repo()
    config = get_config()
    licensee = repo.get_licensee(licensee_id)
    if not licensee:
        return HTMLResponse("Licensee not found", status_code=404)
    revenue = repo.get_license_revenue(licensee_id)
    invoices = repo.get_invoices(entity_type="licensee", entity_id=licensee_id)
    return HTMLResponse(render("licensee_detail.html", licensee=licensee, revenue=revenue, invoices=invoices, config=config))

@router.post("/create", response_class=HTMLResponse)
async def create_licensee(request: Request, company_name: str = Form(...), contact_name: str = Form(...), email: str = Form(...), password: str = Form(...), city_market_slug: str = Form(""), edition_slugs: str = Form("fan,artist,industry"), plan: str = Form("monthly")):
    repo = get_repo()
    config = get_config()
    from weeklyamp.web.security import hash_password
    pw_hash = hash_password(password)
    fee = config.licensing.default_monthly_fee_cents if plan == "monthly" else config.licensing.default_annual_fee_cents
    share = config.licensing.default_revenue_share_pct
    licensee_id = repo.create_licensee(company_name, contact_name, email, pw_hash, city_market_slug, edition_slugs, plan, fee, share)

    # If billing is active, redirect to Manifest checkout
    if config.paid_tiers.enabled and config.licensing.enabled:
        from weeklyamp.billing.licensee_billing import LicenseeBillingManager
        mgr = LicenseeBillingManager(repo, config)
        checkout_url = mgr.create_license_checkout(licensee_id, plan)
        if checkout_url:
            return RedirectResponse(checkout_url, status_code=303)

    return HTMLResponse(f'<div class="alert alert-success">Licensee created (ID: {licensee_id}). Status: pending approval.</div>')

@router.post("/{licensee_id}/status", response_class=HTMLResponse)
async def update_status(licensee_id: int, request: Request, status: str = Form(...)):
    repo = get_repo()
    config = get_config()
    repo.update_licensee_status(licensee_id, status)

    # If activating, run full onboarding
    if status == "active" and config.paid_tiers.enabled:
        from weeklyamp.billing.licensee_billing import LicenseeBillingManager
        mgr = LicenseeBillingManager(repo, config)
        mgr.activate_licensee(licensee_id)

        # Send notification
        licensee = repo.get_licensee(licensee_id)
        if licensee:
            from weeklyamp.notifications.manager import NotificationManager
            NotificationManager(repo).notify_licensee_activated(
                licensee.get("company_name", ""),
                licensee.get("city_market_slug", ""),
            )

    return HTMLResponse(f'<span class="badge badge-info">{status}</span>')


# ---- Franchise Model ----

@router.get("/franchise/territories", response_class=HTMLResponse)
async def franchise_territories(request: Request):
    """View territory map and exclusivity status."""
    repo = get_repo()
    config = get_config()
    if not config.franchise.enabled:
        return HTMLResponse('<div class="alert alert-info">Franchise model not yet active.</div>')
    conn = repo._conn()
    territories = conn.execute(
        """SELECT l.*, em.market_name
           FROM licensees l
           LEFT JOIN edition_markets em ON em.slug = l.city_market_slug
           WHERE l.territory_exclusive = 1
           ORDER BY l.market_tier, em.market_name"""
    ).fetchall()
    conn.close()
    return HTMLResponse(render("franchise_territories.html", territories=[dict(t) for t in territories], config=config))


@router.post("/{licensee_id}/territory", response_class=HTMLResponse)
async def set_territory(licensee_id: int, request: Request, territory_exclusive: int = Form(1), market_tier: str = Form("medium")):
    """Set territory exclusivity and market tier for a licensee."""
    repo = get_repo()
    config = get_config()
    if not config.franchise.enabled:
        return HTMLResponse('<div class="alert alert-warning">Franchise model not active.</div>')
    conn = repo._conn()
    conn.execute(
        "UPDATE licensees SET territory_exclusive = ?, market_tier = ? WHERE id = ?",
        (territory_exclusive, market_tier, licensee_id),
    )
    conn.commit()
    conn.close()
    return HTMLResponse(f'<div class="alert alert-success">Territory updated for licensee {licensee_id}.</div>')


@router.get("/franchise/rollup", response_class=HTMLResponse)
async def franchise_rollup(request: Request):
    """Regional revenue rollup across all franchise territories."""
    repo = get_repo()
    config = get_config()
    if not config.franchise.enabled:
        return HTMLResponse('<div class="alert alert-info">Franchise model not yet active.</div>')
    conn = repo._conn()
    rollup = conn.execute(
        """SELECT l.market_tier, COUNT(*) as licensees,
                  SUM(lr.sponsor_revenue_cents + lr.affiliate_revenue_cents + lr.subscriber_revenue_cents) as total_revenue_cents,
                  SUM(lr.platform_share_cents) as platform_share_cents
           FROM licensees l
           LEFT JOIN license_revenue lr ON lr.licensee_id = l.id
           WHERE l.status = 'active'
           GROUP BY l.market_tier"""
    ).fetchall()
    conn.close()
    return HTMLResponse(render("franchise_rollup.html", rollup=[dict(r) for r in rollup], config=config))
