"""City-license revenue levers: extra lines on the monthly licensee invoice.

Each lever is off until its feature flag is on (see FLAG_METADATA, category
"License revenue"), so with every flag off a licensee's invoice is exactly
what it was before: license fee + platform revenue share.

Charges are positive line items, credits (money DISPATCH owes the licensee)
are negative. Amounts come from ``config.license_revenue``. All of them are
starting points to test against the first real cities, not measured rates.

Months are 'YYYY-MM' strings computed in Python. No SQL date functions, so
SQLite and Postgres agree (see feedback on portability).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from weeklyamp.core.feature_flags import FeatureFlag, enabled as flag_enabled


@dataclass
class ExtrasResult:
    lines: list[dict] = field(default_factory=list)
    # Things the caller must persist once the invoice is actually created.
    launch_fee_month: str = ""

    @property
    def total_cents(self) -> int:
        return sum(line["amount_cents"] for line in self.lines)

    def add(self, flag: str, description: str, amount_cents: int) -> None:
        if amount_cents:
            self.lines.append({"description": description, "amount_cents": int(round(amount_cents)),
                               "lever": flag})


def _month_of(value) -> str:
    """'YYYY-MM' from a timestamp column (datetime or ISO-ish string)."""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")
    return str(value)[:7]


def _months_between(start_month: str, month: str) -> int:
    """Whole months from start_month to month ('2026-01' -> '2026-07' = 6)."""
    try:
        sy, sm = (int(x) for x in start_month.split("-")[:2])
        y, m = (int(x) for x in month.split("-")[:2])
    except (ValueError, AttributeError):
        return 0
    return (y - sy) * 12 + (m - sm)


def _money(cents: float) -> str:
    return f"${cents / 100:,.2f}".replace(".00", "")


class LicenseExtras:
    """Compute the revenue-lever lines for one licensee and month."""

    def __init__(self, repo, config, is_enabled: Optional[Callable[[str], bool]] = None) -> None:
        self.repo = repo
        self.config = config
        self.rc = config.license_revenue
        # Injectable for tests; defaults to the real flag lookup.
        self._enabled = is_enabled or (lambda name: flag_enabled(name, repo=repo))

    # ---- public -------------------------------------------------------

    def compute(self, licensee: dict, month: str, base_platform_cents: int,
                sponsor_revenue_cents: int = 0) -> ExtrasResult:
        """Return the extra invoice lines for ``licensee`` in ``month``.

        ``base_platform_cents`` is what the invoice already charges (fee +
        platform share); the platform minimum tops up against it.
        ``sponsor_revenue_cents`` is the city's ad revenue for the month,
        used by managed sales.
        """
        r = ExtrasResult()
        fee = int(licensee.get("license_fee_cents") or 0)

        self._launch_fee(r, licensee, month)
        self._market_pricing(r, licensee, fee)
        self._managed_sales(r, licensee, sponsor_revenue_cents)
        self._venue_listings(r, licensee, month)
        self._ticket_fee(r, licensee, month)
        self._master_license(r, licensee)

        # Credits go last but before the minimum, which is measured on what
        # DISPATCH actually charges (credits don't count against it).
        self._network_ads(r, licensee, month)
        self._funnel_bounty(r, licensee, month)
        self._platform_minimum(r, licensee, month, base_platform_cents)
        return r

    # ---- charges ------------------------------------------------------

    def _launch_fee(self, r: ExtrasResult, lic: dict, month: str) -> None:
        if not self._enabled(FeatureFlag.LAUNCH_FEE) or lic.get("launch_fee_billed_month"):
            return
        # Only a brand-new city pays it: anyone already invoiced launched
        # before the fee existed, and switching the flag on must not
        # back-charge them.
        if self.repo.get_invoices(entity_type="licensee", entity_id=lic["id"]):
            return
        r.add(FeatureFlag.LAUNCH_FEE, "City launch fee (one-time)", self.rc.launch_fee_cents)
        if self.rc.launch_fee_cents:
            r.launch_fee_month = month

    def _market_pricing(self, r: ExtrasResult, lic: dict, fee: int) -> None:
        if not self._enabled(FeatureFlag.MARKET_PRICING):
            return
        tier = (lic.get("market_tier") or "medium").lower()
        mult = float(self.rc.market_multipliers.get(tier, 1.0))
        if mult != 1.0 and fee:
            r.add(FeatureFlag.MARKET_PRICING,
                  f"Market tier: {tier} (license fee x{mult:g})", fee * (mult - 1.0))
        if lic.get("territory_exclusive"):
            r.add(FeatureFlag.MARKET_PRICING, "Territory exclusivity", self.rc.exclusivity_fee_cents)

    def _managed_sales(self, r: ExtrasResult, lic: dict, sponsor_cents: int) -> None:
        if not self._enabled(FeatureFlag.MANAGED_SALES) or not lic.get("managed_sales"):
            return
        tier_pct = float(lic.get("revenue_share_pct") or 0.0)
        managed_pct = float(self.rc.managed_sales_platform_pct)
        extra_pct = max(0.0, managed_pct - tier_pct)
        if sponsor_cents and extra_pct:
            r.add(FeatureFlag.MANAGED_SALES,
                  f"Managed ad sales ({managed_pct:g}% platform share, was {tier_pct:g}%)",
                  sponsor_cents * extra_pct / 100)

    def _venue_listings(self, r: ExtrasResult, lic: dict, month: str) -> None:
        if not self._enabled(FeatureFlag.VENUE_LISTINGS):
            return
        live = [
            v for v in self.repo.get_venue_listings(lic["id"])
            if v.get("status") == "active"
            and (v.get("start_month") or "") <= month
            and (not v.get("end_month") or v["end_month"] >= month)
        ]
        gross = sum(int(v.get("monthly_price_cents") or 0) for v in live)
        pct = float(self.rc.venue_listing_platform_pct)
        if gross:
            r.add(FeatureFlag.VENUE_LISTINGS,
                  f"Venue listings: {len(live)} live, {_money(gross)} sold ({pct:g}% platform share)",
                  gross * pct / 100)

    def _ticket_fee(self, r: ExtrasResult, lic: dict, month: str) -> None:
        if not self._enabled(FeatureFlag.TICKET_FEE):
            return
        n = sum(1 for reg in self.repo.get_paid_ticket_registrations(lic["id"])
                if _month_of(reg.get("created_at")) == month)
        if n:
            r.add(FeatureFlag.TICKET_FEE,
                  f"Ticket fee: {n} paid ticket{'s' if n != 1 else ''} x {_money(self.rc.ticket_fee_cents)}",
                  n * self.rc.ticket_fee_cents)

    def _master_license(self, r: ExtrasResult, lic: dict) -> None:
        if not self._enabled(FeatureFlag.MASTER_LICENSE) or not lic.get("is_master"):
            return
        r.add(FeatureFlag.MASTER_LICENSE, "Regional master license fee", self.rc.master_regional_fee_cents)
        subs = [s for s in self.repo.get_sub_licensees(lic["id"]) if s.get("status") == "active"]
        sub_fees = sum(int(s.get("license_fee_cents") or 0) for s in subs)
        pct = float(self.rc.master_override_pct)
        if sub_fees:
            r.add(FeatureFlag.MASTER_LICENSE,
                  f"Master override credit: {pct:g}% of {len(subs)} sub-cit{'ies' + chr(39) if len(subs) != 1 else 'y' + chr(39) + 's'} fees",
                  -sub_fees * pct / 100)

    # ---- credits ------------------------------------------------------

    def _network_ads(self, r: ExtrasResult, lic: dict, month: str) -> None:
        if not self._enabled(FeatureFlag.NETWORK_ADS):
            return
        active_ids = [l["id"] for l in self.repo.get_licensees(status="active")]
        credit = 0.0
        count = 0
        for c in self.repo.get_network_campaigns(month):
            if c.get("status") == "cancelled":
                continue
            raw = (c.get("licensee_ids") or "all").strip()
            cities = active_ids if raw == "all" else [
                int(x) for x in raw.split(",") if x.strip().isdigit()]
            if lic["id"] not in cities or not cities:
                continue
            share = int(c.get("amount_cents") or 0) / len(cities)
            credit += share * float(self.rc.network_licensee_cut_pct) / 100
            count += 1
        if credit:
            r.add(FeatureFlag.NETWORK_ADS,
                  f"Network ad revenue credit: {count} national campaign{'s' if count != 1 else ''} "
                  f"({self.rc.network_licensee_cut_pct:g}% of this city's share)",
                  -credit)

    def _funnel_bounty(self, r: ExtrasResult, lic: dict, month: str) -> None:
        if not self._enabled(FeatureFlag.FUNNEL_BOUNTY):
            return
        conv = self.repo.get_funnel_conversions(licensee_id=lic["id"], month=month)
        total = sum(int(c.get("bounty_cents") or 0) for c in conv)
        if total:
            r.add(FeatureFlag.FUNNEL_BOUNTY,
                  f"Finder's fee credit: {len(conv)} signup{'s' if len(conv) != 1 else ''} to AMP / EDGE / RISE",
                  -total)

    # ---- floor --------------------------------------------------------

    def _platform_minimum(self, r: ExtrasResult, lic: dict, month: str, base_cents: int) -> None:
        if not self._enabled(FeatureFlag.PLATFORM_MINIMUM):
            return
        start = _month_of(lic.get("activated_at") or lic.get("created_at"))
        if not start or _months_between(start, month) < self.rc.platform_minimum_after_months:
            return
        charged = base_cents + sum(l["amount_cents"] for l in r.lines if l["amount_cents"] > 0)
        gap = self.rc.platform_minimum_cents - charged
        if gap > 0:
            r.add(FeatureFlag.PLATFORM_MINIMUM,
                  f"Platform minimum top-up (floor {_money(self.rc.platform_minimum_cents)}/mo)", gap)


def bounty_for(config, product: str) -> int:
    """Finder's fee in cents for a signup to ``product`` (amp / edge / rise)."""
    return int(config.license_revenue.funnel_bounties_cents.get((product or "").lower(), 0))
