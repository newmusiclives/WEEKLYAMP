"""Tests for the city-license tier ladder.

Three prices for the same product were live at once: the public page
offered $50/$100/$150 with the licensee keeping 25/50/75%, the config
said $150/mo with a 20% platform share, and the seeded licensee row said
$99/mo. The admin create form read the config, so a Starter signup was
created on the default plan's terms.

These lock down the parts that were wrong:
  1. A tier is billed at the tier the licensee chose.
  2. platform_share_pct is *our* cut; the licensee keeps the remainder.
  3. Delivery beyond the tier allowance is charged, because email is most
     of the marginal cost of serving a location.
"""

from __future__ import annotations

import pytest

from weeklyamp.core.config import load_config
from weeklyamp.core.models import LicensingConfig


@pytest.fixture()
def lic() -> LicensingConfig:
    return LicensingConfig()


# --- the ladder -------------------------------------------------------


def test_three_tiers_are_defined(lic):
    assert [t.slug for t in lic.tiers] == ["starter", "growth", "pro"]


def test_paying_more_keeps_more(lic):
    """The ladder's whole premise: a higher fee buys a bigger split."""
    tiers = sorted(lic.tiers, key=lambda t: t.monthly_fee_cents)
    shares = [t.licensee_share_pct for t in tiers]
    assert shares == sorted(shares), shares
    assert shares == [25.0, 50.0, 75.0]


def test_platform_share_is_the_complement(lic):
    for t in lic.tiers:
        assert t.platform_share_pct + t.licensee_share_pct == 100.0


def test_allowance_grows_with_the_tier(lic):
    tiers = sorted(lic.tiers, key=lambda t: t.monthly_fee_cents)
    allowances = [t.included_sends for t in tiers]
    assert allowances == sorted(allowances)
    assert allowances == [2500, 6000, 12000]


def test_annual_is_ten_months(lic):
    """Two months free — the old $999 annual was 45% off the monthly rate."""
    for t in lic.tiers:
        assert t.annual_fee_cents == t.monthly_fee_cents * 10, t.slug


def test_public_page_prices_match_config(lic):
    """The page is the promise; config is what actually bills."""
    by_slug = {t.slug: t for t in lic.tiers}
    assert by_slug["starter"].monthly_fee_cents == 5000
    assert by_slug["growth"].monthly_fee_cents == 10000
    assert by_slug["pro"].monthly_fee_cents == 19900


# --- tier lookup ------------------------------------------------------


def test_tier_lookup_by_slug(lic):
    assert lic.tier("pro").monthly_fee_cents == 19900


def test_unknown_tier_falls_back_to_default(lic):
    assert lic.tier("enterprise").slug == lic.default_tier


def test_blank_tier_falls_back_to_default(lic):
    assert lic.tier("").slug == lic.default_tier
    assert lic.tier().slug == lic.default_tier


def test_tier_lookup_is_case_insensitive(lic):
    assert lic.tier("PRO").slug == "pro"


# --- backwards-compatible accessors -----------------------------------


def test_legacy_accessors_track_the_default_tier(lic):
    default = lic.tier()
    assert lic.default_monthly_fee_cents == default.monthly_fee_cents
    assert lic.default_annual_fee_cents == default.annual_fee_cents
    assert lic.default_revenue_share_pct == default.platform_share_pct


# --- delivery overage -------------------------------------------------


def test_no_overage_inside_the_allowance(lic):
    assert lic.monthly_overage_cents("growth", 6000) == 0
    assert lic.monthly_overage_cents("growth", 1) == 0


def test_overage_charged_beyond_the_allowance(lic):
    # 8,000 sends on Growth = 2,000 over = 2 blocks x $15
    assert lic.monthly_overage_cents("growth", 8000) == 3000


def test_partial_block_is_billed_whole(lic):
    """A started 1,000 isn't given away."""
    assert lic.monthly_overage_cents("growth", 6001) == 1500
    assert lic.monthly_overage_cents("growth", 6999) == 1500


def test_overage_covers_delivery_cost(lic):
    """$15 per 1,000/mo against a $9.60 cost — growth must not go
    underwater as a licensee's list grows."""
    cost_per_1k_cents = 12 * 100 * 0.80 / 100  # 12 sends x $0.80/1k = $9.60
    assert lic.overage_per_1k_cents / 100.0 > cost_per_1k_cents


def test_large_list_on_pro_is_covered():
    """The failure mode the flat fee had: a big list with a modest fee.
    Pro at 25,000 sends must bill above the ~$247/mo cost to serve."""
    lic = LicensingConfig()
    sends = 25000
    fee = lic.tier("pro").monthly_fee_cents
    overage = lic.monthly_overage_cents("pro", sends)
    ai_cents = 680          # 36 issues x ~$0.19, measured
    email_cents = int(12 * sends / 1000 * 80)
    assert fee + overage > ai_cents + email_cents


def test_shipped_yaml_loads_the_tiers():
    """config/default.yaml must parse into the same ladder."""
    cfg = load_config()
    assert [t.slug for t in cfg.licensing.tiers] == ["starter", "growth", "pro"]
    assert cfg.licensing.tier("pro").monthly_fee_cents == 19900
    assert cfg.licensing.overage_per_1k_cents == 1500
