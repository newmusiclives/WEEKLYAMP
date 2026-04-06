"""Analytics tools — NPS, content reports, revenue forecasting, media kit."""

from __future__ import annotations
import json
import logging
from datetime import datetime
from weeklyamp.db.repository import Repository

logger = logging.getLogger(__name__)


def calculate_nps(repo: Repository) -> dict:
    """Calculate Net Promoter Score from survey data.
    Returns {score, promoters, passives, detractors, total_responses}.
    """
    conn = repo._conn()
    rows = conn.execute("SELECT reason FROM unsubscribe_surveys ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()

    # Simple NPS proxy from unsubscribe reasons
    # In a real system, this would come from dedicated NPS surveys
    total = len(rows)
    if total == 0:
        return {"score": 0, "promoters": 0, "passives": 0, "detractors": 0, "total_responses": 0}

    detractors = sum(1 for r in rows if dict(r).get("reason") in ("not_relevant", "too_many_emails"))
    passives = sum(1 for r in rows if dict(r).get("reason") in ("inbox_overload", "other"))
    promoters = total - detractors - passives

    score = round(((promoters - detractors) / total) * 100) if total > 0 else 0
    return {"score": score, "promoters": promoters, "passives": passives, "detractors": detractors, "total_responses": total}


def generate_content_report(repo: Repository) -> dict:
    """Generate per-section content performance report."""
    sections = repo.get_all_sections()
    report = []
    for section in sections[:20]:
        slug = section.get("slug", "")
        display = section.get("display_name", slug)
        report.append({
            "slug": slug,
            "display_name": display,
            "category": section.get("category", ""),
            "word_count_target": section.get("target_word_count", 300),
            "type": section.get("section_type", "core"),
        })
    return {"sections": report, "total": len(report)}


def forecast_revenue(repo: Repository, months: int = 12, growth_rate: float = 0.10) -> list[dict]:
    """Forecast revenue for next N months based on current metrics and growth rate."""
    subscriber_count = repo.get_subscriber_count()
    revenue = repo.get_revenue_summary()

    sponsor_monthly = revenue.get("sponsor", {}).get("paid_cents", 0) / 100
    tier_monthly = revenue.get("tier", {}).get("mrr_cents", 0) / 100
    affiliate_monthly = revenue.get("affiliate", {}).get("total_revenue", 0) / 100

    current_monthly = sponsor_monthly + tier_monthly + affiliate_monthly
    if current_monthly == 0:
        # Estimate based on subscriber count
        current_monthly = subscriber_count * 2  # $2/sub/month estimate

    forecasts = []
    cumulative = 0
    for m in range(1, months + 1):
        multiplier = (1 + growth_rate) ** (m - 1)
        projected_subs = round(subscriber_count * multiplier)
        projected_rev = round(current_monthly * multiplier, 2)
        cumulative += projected_rev
        forecasts.append({
            "month": m,
            "subscribers": projected_subs,
            "monthly_revenue": projected_rev,
            "cumulative_revenue": round(cumulative, 2),
        })

    return forecasts


def generate_media_kit_text(repo: Repository, config) -> str:
    """Generate media kit content for sponsor pitches."""
    subscriber_count = repo.get_subscriber_count()
    editions = repo.get_editions()

    kit = f"""TRUEFANS SIGNAL — MEDIA KIT
{'=' * 50}

OVERVIEW
TrueFans SIGNAL is a music industry newsletter platform
publishing {len(editions)} editions, 3x weekly.

AUDIENCE
Total Subscribers: {subscriber_count:,}
"""
    for ed in editions:
        kit += f"  • {ed['name']}: {ed.get('audience', 'Music professionals and fans')}\n"

    kit += f"""
SPONSORSHIP OPTIONS
  • Top Position: Premium above-the-fold placement (1.5x CPM)
  • Mid Position: In-content native placement (1.0x CPM)
  • Bottom Position: End-of-newsletter placement (0.7x CPM)

PRICING
  Base CPM: ${config.sponsor_portal.base_cpm:.2f}
  Weekly discount: {int((1-config.sponsor_portal.weekly_discount)*100)}% off
  Monthly discount: {int((1-config.sponsor_portal.monthly_discount)*100)}% off

CONTACT
  Email: sales@truefansnewsletters.com
  Advertise page: {config.site_domain}/advertise

{'=' * 50}
Generated {datetime.now().strftime('%B %d, %Y')}
"""
    return kit
