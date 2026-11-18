"""Dynamic rate card engine for sponsor pricing and slot availability."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


class RateCardEngine:
    """Calculate dynamic sponsor rates based on audience metrics and config."""

    POSITIONS = ["top", "mid", "bottom"]
    POSITION_LABELS = {"top": "Premium Top", "mid": "Mid-Content", "bottom": "Footer"}
    # Mid-Content is the base CPM ($35). Premium Top and Footer are set
    # relative to it so the card reads $50 / $35 / $20 (2026-11-17 pricing).
    POSITION_MULTIPLIERS = {"top": 50 / 35, "mid": 1.0, "bottom": 20 / 35}
    MIN_PRICED_LIST = 1000

    def __init__(self, repo, config) -> None:
        self.repo = repo
        self.config = config  # SponsorPortalConfig

    def calculate_rates(self, edition_slug: str = "") -> dict:
        """Calculate CPM rates based on actual subscriber counts and open rates.

        Returns dict keyed by position with {cpm, per_issue, per_week, per_month}.
        """
        base_cpm = self.config.base_cpm
        weekly_discount = self.config.weekly_discount
        monthly_discount = self.config.monthly_discount

        # Price at the real list size once it passes 1,000. Below that the
        # card prices per 1,000 subscribers: a near-empty pre-launch list
        # otherwise shows $0 for every placement. ``priced_at`` tells the
        # page which size the prices assume.
        sub_count = self.repo.get_subscriber_count()
        priced_at = max(sub_count, self.MIN_PRICED_LIST)
        thousands = priced_at / 1000.0

        rates = {}
        for pos in self.POSITIONS:
            multiplier = self.POSITION_MULTIPLIERS[pos]
            cpm = round(base_cpm * multiplier, 2)
            per_issue = round(cpm * thousands, 2)
            per_week = round(per_issue * 3 * weekly_discount, 2)   # 3 issues/week
            per_month = round(per_issue * 12 * monthly_discount, 2)  # ~12 issues/month

            rates[pos] = {
                "label": self.POSITION_LABELS[pos],
                "cpm": cpm,
                "per_issue": per_issue,
                "per_week": per_week,
                "per_month": per_month,
                "multiplier": multiplier,
                "priced_at": priced_at,
                "per_thousand": priced_at == self.MIN_PRICED_LIST and sub_count < self.MIN_PRICED_LIST,
            }

        return rates

    # Worked examples on /advertise. These are illustrative list sizes, not
    # DISPATCH's audience, and the funnel uses the same default assumptions
    # as the page's estimator, so the page never states a measured result.
    EXAMPLE_LIST_SIZES = (1000, 2500, 10000)
    EXAMPLE_ASSUMPTIONS = {"open_pct": 40.0, "click_pct": 5.0, "conv_pct": 3.0, "value": 100.0}

    def example_scenarios(self, sizes: tuple[int, ...] = EXAMPLE_LIST_SIZES) -> list[dict]:
        """Price every placement and package at example list sizes, and
        run a Premium Top weekly campaign through the example funnel."""
        weekly_discount = self.config.weekly_discount
        monthly_discount = self.config.monthly_discount
        a = self.EXAMPLE_ASSUMPTIONS

        scenarios = []
        for size in sizes:
            thousands = size / 1000.0
            rows = []
            for pos in self.POSITIONS:
                cpm = round(self.config.base_cpm * self.POSITION_MULTIPLIERS[pos], 2)
                per_issue = round(cpm * thousands, 2)
                rows.append({
                    "position": pos,
                    "label": self.POSITION_LABELS[pos],
                    "cpm": cpm,
                    "per_issue": per_issue,
                    "per_week": round(per_issue * 3 * weekly_discount, 2),
                    "per_month": round(per_issue * 12 * monthly_discount, 2),
                })

            top = rows[0]
            sends = size * 3
            opens = sends * a["open_pct"] / 100
            clicks = opens * a["click_pct"] / 100
            customers = clicks * a["conv_pct"] / 100
            revenue = customers * a["value"]
            cost = top["per_week"]
            scenarios.append({
                "subscribers": size,
                "rows": rows,
                "campaign": {
                    "label": f"{top['label']}, weekly (3 issues)",
                    "cost": cost,
                    "sends": sends,
                    "opens": round(opens),
                    "clicks": round(clicks),
                    "cpc": round(cost / clicks + 1e-9, 2) if clicks else None,
                    "customers": round(customers, 1),
                    "revenue": round(revenue, 2),
                    "net": round(revenue - cost, 2),
                },
            })
        return scenarios

    def get_available_slots(self, weeks_ahead: int = 4) -> list[dict]:
        """Check upcoming issues for open sponsor slots.

        Returns list of available date/edition/position combos.
        """
        editions = self.repo.get_editions(active_only=True)
        all_blocks = self.repo.get_all_sponsor_blocks()

        # Build set of filled slots
        filled = set()
        for b in all_blocks:
            filled.add((b["edition_slug"], b["edition_number"], b["position"]))

        available = []
        today = datetime.now().date()

        for week_offset in range(weeks_ahead):
            week_start = today + timedelta(weeks=week_offset)
            week_label = week_start.strftime("%b %d") + " - " + (week_start + timedelta(days=6)).strftime("%b %d, %Y")

            for ed in editions:
                for edition_num in [1, 2, 3]:
                    for pos in self.POSITIONS:
                        key = (ed["slug"], edition_num, pos)
                        if key not in filled:
                            available.append({
                                "week_label": week_label,
                                "week_offset": week_offset,
                                "edition_slug": ed["slug"],
                                "edition_name": ed.get("name", ed["slug"]),
                                "edition_number": edition_num,
                                "position": pos,
                                "position_label": self.POSITION_LABELS[pos],
                            })

        return available

    def get_media_kit_data(self) -> dict:
        """Compile data for the public media kit / advertise page."""
        sub_count = self.repo.get_subscriber_count()

        # The media kit lists DISPATCH's five editions from the product
        # definition in code, not from newsletter_editions: a prod DB that
        # is missing a row (Venue, 2026-11) must not drop an edition from
        # what advertisers are told they can buy. Four audience editions go
        # out 3x a week; the Single Daily Action is a different format.
        from weeklyamp.core.database import DEFAULT_EDITIONS

        edition_descriptions = {
            "fan": "Passionate music fans who discover, share, and support artists",
            "artist": "Independent and emerging artists building their careers",
            "venue": "Venue owners, bookers and talent buyers running live music rooms",
            "industry": "Music industry professionals, labels, and decision-makers",
            "daily-action": "Independent artists building a direct fan base, one thirty-second action every weekday",
        }

        edition_data = []
        for slug, name, tagline, _desc, audience, *_rest in DEFAULT_EDITIONS:
            edition_data.append({
                "slug": slug,
                "name": name,
                "tagline": tagline,
                "description": edition_descriptions.get(slug) or audience,
                "daily": slug == "daily-action",
                "subscriber_count": sub_count // max(len(DEFAULT_EDITIONS), 1),
            })
        audience_editions = [e for e in edition_data if not e["daily"]]
        daily_edition = next((e for e in edition_data if e["daily"]), None)

        # Engagement rates come from measured sends only. Before the first
        # send there is nothing to report, and these figures are published to
        # advertisers on the public media kit — a placeholder here is a false
        # performance claim to someone deciding whether to buy ad space.
        measured = self.repo.get_average_engagement()
        avg_open_rate = measured["avg_open_rate"] if measured else None
        avg_click_rate = measured["avg_click_rate"] if measured else None

        rates = self.calculate_rates()
        available_slots = self.get_available_slots(weeks_ahead=4)

        return {
            "total_subscribers": sub_count,
            # None means "not measured yet" — the template must omit the tile
            # rather than render a number.
            "avg_open_rate": avg_open_rate,
            "avg_click_rate": avg_click_rate,
            "issues_measured": measured["issues_measured"] if measured else 0,
            "issues_per_week": 3,
            "editions": edition_data,
            "rates": rates,
            "rates_priced_at": next(iter(rates.values()))["priced_at"],
            "rates_per_thousand": next(iter(rates.values()))["per_thousand"],
            "edition_count": len(edition_data),
            "audience_editions": audience_editions,
            "daily_edition": daily_edition,
            "examples": self.example_scenarios(),
            "example_assumptions": self.EXAMPLE_ASSUMPTIONS,
            "available_slots": available_slots,
            "available_slot_count": len(available_slots),
        }
