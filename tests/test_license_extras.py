"""City-license revenue levers (billing/license_extras.py).

Every lever is behind its own feature flag. With all flags off the licensee
invoice must be exactly what it was (fee + platform share), so the first
test pins that; the rest switch on one lever at a time.
"""

from __future__ import annotations

import json

import pytest

from weeklyamp.billing.license_extras import LicenseExtras, _months_between
from weeklyamp.core.feature_flags import FLAG_DEPENDENCIES, FLAG_METADATA, FeatureFlag
from weeklyamp.core.models import AppConfig

LEVERS = [
    FeatureFlag.NETWORK_ADS, FeatureFlag.FUNNEL_BOUNTY, FeatureFlag.LAUNCH_FEE,
    FeatureFlag.MARKET_PRICING, FeatureFlag.VENUE_LISTINGS, FeatureFlag.MANAGED_SALES,
    FeatureFlag.TICKET_FEE, FeatureFlag.MASTER_LICENSE, FeatureFlag.PLATFORM_MINIMUM,
]
MONTH = "2026-12"


@pytest.fixture()
def cfg():
    c = AppConfig()
    c.licensing.enabled = True
    return c


def _licensee(repo, name, fee=15000, share=50.0, market="", **cols):
    lid = repo.create_licensee(name, "Pat", f"{name.lower().replace(' ', '')}@example.com", "x",
                               market, "fan,artist,venue,industry", "monthly", fee, share)
    sets = {"status": "active", "activated_at": "2026-01-15 00:00:00", "territory_exclusive": 0, **cols}
    conn = repo._conn()
    conn.execute(
        "UPDATE licensees SET " + ", ".join(f"{k} = ?" for k in sets) + " WHERE id = ?",
        (*sets.values(), lid))
    conn.commit()
    conn.close()
    return repo.get_licensee(lid)


def _engine(repo, cfg, *on):
    return LicenseExtras(repo, cfg, is_enabled=lambda name: name in on)


def _amounts(result):
    return {line["lever"]: line["amount_cents"] for line in result.lines}


def test_all_flags_off_adds_nothing(repo, cfg):
    lic = _licensee(repo, "Quiet City", market_tier="major", territory_exclusive=1, is_master=1)
    repo.create_venue_listing(lic["id"], "The Room", 3900, MONTH)
    repo.create_funnel_conversion(lic["id"], "amp", MONTH, 2000)
    r = _engine(repo, cfg).compute(lic, MONTH, base_platform_cents=0, sponsor_revenue_cents=50000)
    assert r.lines == []
    assert r.total_cents == 0


def test_every_lever_is_a_listed_flag():
    for flag in LEVERS:
        label, category, desc = FLAG_METADATA[flag]
        assert category == "License revenue" and label and desc
    assert FLAG_DEPENDENCIES[FeatureFlag.MASTER_LICENSE] == (FeatureFlag.FRANCHISE,)
    assert FLAG_DEPENDENCIES[FeatureFlag.TICKET_FEE] == (FeatureFlag.EVENTS,)


def test_launch_fee_bills_once(repo, cfg):
    lic = _licensee(repo, "New City")
    r = _engine(repo, cfg, FeatureFlag.LAUNCH_FEE).compute(lic, MONTH, 15000)
    assert _amounts(r)[FeatureFlag.LAUNCH_FEE] == 75000
    assert r.launch_fee_month == MONTH
    repo.mark_launch_fee_billed(lic["id"], MONTH)
    r2 = _engine(repo, cfg, FeatureFlag.LAUNCH_FEE).compute(repo.get_licensee(lic["id"]), "2027-01", 15000)
    assert r2.lines == []


def test_launch_fee_never_back_charges_an_invoiced_city(repo, cfg):
    lic = _licensee(repo, "Old City")
    repo.create_invoice("LIC-OLD-1", "licensee", lic["id"], 15000)
    assert _engine(repo, cfg, FeatureFlag.LAUNCH_FEE).compute(lic, MONTH, 15000).lines == []


def test_market_tier_and_exclusivity(repo, cfg):
    lic = _licensee(repo, "Big City", fee=15000, market_tier="major", territory_exclusive=1)
    a = _amounts(_engine(repo, cfg, FeatureFlag.MARKET_PRICING).compute(lic, MONTH, 15000))
    lines = _engine(repo, cfg, FeatureFlag.MARKET_PRICING).compute(lic, MONTH, 15000).lines
    assert [l["amount_cents"] for l in lines] == [15000, 10000]  # x2.0 adds one more fee; exclusivity $100
    small = _licensee(repo, "Small Town", market_tier="small")
    assert _engine(repo, cfg, FeatureFlag.MARKET_PRICING).compute(small, MONTH, 15000).lines == []


def test_managed_sales_raises_platform_share(repo, cfg):
    lic = _licensee(repo, "Managed City", share=50.0, managed_sales=1)
    r = _engine(repo, cfg, FeatureFlag.MANAGED_SALES).compute(lic, MONTH, 15000, sponsor_revenue_cents=100000)
    assert _amounts(r)[FeatureFlag.MANAGED_SALES] == 10000  # 60% - 50% of $1,000
    other = _licensee(repo, "Self Sold", share=50.0)
    assert _engine(repo, cfg, FeatureFlag.MANAGED_SALES).compute(other, MONTH, 15000, 100000).lines == []


def test_venue_listings_bill_only_live_months(repo, cfg):
    lic = _licensee(repo, "Venue City")
    repo.create_venue_listing(lic["id"], "Room A", 3900, "2026-11")
    repo.create_venue_listing(lic["id"], "Room B", 4900, "2027-01")   # not started yet
    ended = repo.create_venue_listing(lic["id"], "Room C", 3900, "2026-01")
    repo.set_venue_listing_status(ended, "cancelled", "2026-06")
    r = _engine(repo, cfg, FeatureFlag.VENUE_LISTINGS).compute(lic, MONTH, 15000)
    assert _amounts(r)[FeatureFlag.VENUE_LISTINGS] == 1950  # 50% of $39


def test_ticket_fee_counts_paid_tickets_in_month(repo, cfg):
    lic = _licensee(repo, "Show City")
    conn = repo._conn()
    eid = conn.execute("INSERT INTO events (title, licensee_id) VALUES (?, ?)", ("Gig", lic["id"])).lastrowid
    rows = [("a@x.com", "paid", "2026-12-03 10:00:00"), ("b@x.com", "paid", "2026-12-20 10:00:00"),
            ("c@x.com", "pending", "2026-12-21 10:00:00"), ("d@x.com", "paid", "2026-11-30 10:00:00")]
    for email, pay, at in rows:
        conn.execute("INSERT INTO event_registrations (event_id, email, payment_status, created_at) VALUES (?, ?, ?, ?)",
                     (eid, email, pay, at))
    conn.commit()
    conn.close()
    r = _engine(repo, cfg, FeatureFlag.TICKET_FEE).compute(lic, MONTH, 15000)
    assert _amounts(r)[FeatureFlag.TICKET_FEE] == 200


def test_master_license_fee_and_override(repo, cfg):
    master = _licensee(repo, "Region Co", fee=30000, is_master=1)
    _licensee(repo, "Sub One", fee=15000, parent_franchise_id=master["id"])
    _licensee(repo, "Sub Two", fee=5000, parent_franchise_id=master["id"])
    lines = _engine(repo, cfg, FeatureFlag.MASTER_LICENSE).compute(master, MONTH, 30000).lines
    assert [l["amount_cents"] for l in lines] == [50000, -2000]  # $500 fee; 10% of $200
    assert "2 sub-cities' fees" in lines[1]["description"]


def test_network_ads_credit_split_across_cities(repo, cfg):
    a = _licensee(repo, "City A")
    b = _licensee(repo, "City B")
    repo.create_network_campaign("Gear Co", MONTH, 100000)                 # all cities
    repo.create_network_campaign("Label X", MONTH, 40000, str(a["id"]))     # city A only
    gone = repo.create_network_campaign("Pulled", MONTH, 999999)
    repo.set_network_campaign_status(gone, "cancelled")
    ra = _amounts(_engine(repo, cfg, FeatureFlag.NETWORK_ADS).compute(a, MONTH, 15000))
    rb = _amounts(_engine(repo, cfg, FeatureFlag.NETWORK_ADS).compute(b, MONTH, 15000))
    assert ra[FeatureFlag.NETWORK_ADS] == -(10000 + 8000)   # 20% of $500, 20% of $400
    assert rb[FeatureFlag.NETWORK_ADS] == -10000


def test_funnel_bounty_credit(repo, cfg):
    lic = _licensee(repo, "Funnel City")
    repo.create_funnel_conversion(lic["id"], "amp", MONTH, 2000)
    repo.create_funnel_conversion(lic["id"], "edge", MONTH, 1500)
    repo.create_funnel_conversion(lic["id"], "amp", "2026-11", 2000)
    r = _engine(repo, cfg, FeatureFlag.FUNNEL_BOUNTY).compute(lic, MONTH, 15000)
    assert _amounts(r)[FeatureFlag.FUNNEL_BOUNTY] == -3500


def test_platform_minimum_after_ramp(repo, cfg):
    lic = _licensee(repo, "Slow City", fee=5000, share=75.0)
    r = _engine(repo, cfg, FeatureFlag.PLATFORM_MINIMUM).compute(lic, MONTH, base_platform_cents=5000)
    assert _amounts(r)[FeatureFlag.PLATFORM_MINIMUM] == 5000   # floor $100 - $50 charged
    young = _licensee(repo, "Young City", fee=5000, activated_at="2026-10-01 00:00:00")
    assert _engine(repo, cfg, FeatureFlag.PLATFORM_MINIMUM).compute(young, MONTH, 5000).lines == []
    assert _months_between("2026-06", "2026-12") == 6


def test_invoice_includes_levers_and_marks_launch_fee(repo, cfg, monkeypatch):
    from weeklyamp.billing import license_extras
    from weeklyamp.billing.invoices import InvoiceManager
    on = {FeatureFlag.LAUNCH_FEE, FeatureFlag.FUNNEL_BOUNTY}
    monkeypatch.setattr(license_extras, "flag_enabled", lambda name, repo=None: name in on)
    lic = _licensee(repo, "Billed City", fee=15000)
    repo.create_funnel_conversion(lic["id"], "amp", MONTH, 2000)
    inv_id = InvoiceManager(repo, cfg).generate_licensee_invoice(lic["id"], MONTH)
    inv = next(i for i in repo.get_invoices(entity_type="licensee") if i["id"] == inv_id)
    assert inv["amount_cents"] == 15000 + 75000 - 2000
    descs = [l["description"] for l in json.loads(inv["line_items_json"])]
    assert any("launch fee" in d for d in descs) and any("Finder's fee" in d for d in descs)
    assert repo.get_licensee(lic["id"])["launch_fee_billed_month"] == MONTH


def test_invoice_never_goes_negative(repo, cfg, monkeypatch):
    from weeklyamp.billing import license_extras
    from weeklyamp.billing.invoices import InvoiceManager
    monkeypatch.setattr(license_extras, "flag_enabled", lambda name, repo=None: name == FeatureFlag.NETWORK_ADS)
    lic = _licensee(repo, "Credit City", fee=5000)
    repo.create_network_campaign("Big Brand", MONTH, 1000000)  # 20% of $10,000 = $2,000 credit
    inv_id = InvoiceManager(repo, cfg).generate_licensee_invoice(lic["id"], MONTH)
    inv = next(i for i in repo.get_invoices(entity_type="licensee") if i["id"] == inv_id)
    assert inv["amount_cents"] == 0
    assert "Credit due to licensee: $1,950.00" in inv["notes"]


def test_admin_page_renders(client):
    r = client.get("/admin/license-revenue")
    assert r.status_code == 200
    assert "License Revenue Levers" in r.text
    import html
    for flag in LEVERS:
        assert FLAG_METADATA[flag][0].replace("'", "&#39;") in r.text
