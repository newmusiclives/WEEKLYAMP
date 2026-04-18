"""Advanced analytics routes — NPS, reports, forecasting, media kit."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from weeklyamp.web.deps import get_config, get_repo, render

router = APIRouter()


@router.get("/cohorts")
async def cohorts_dashboard(request: Request):
    """Subscriber retention cohort dashboard.

    Buckets active subscribers by signup month and reports how many
    are still active and how many have unsubscribed for each cohort.
    Optional ?source=<channel> filter narrows by source_channel.

    Returns JSON. The HTML dashboard can be added later — for now
    this is consumable by an internal tool or a curl call.
    """
    repo = get_repo()
    source = request.query_params.get("source", "").strip()
    conn = repo._conn()

    sql = (
        "SELECT subscribed_at, status, source_channel FROM subscribers "
        "WHERE subscribed_at IS NOT NULL"
    )
    params: tuple = ()
    if source:
        sql += " AND source_channel = ?"
        params = (source,)
    try:
        rows = conn.execute(sql, params).fetchall()
        rows = [dict(r) for r in rows]
    except Exception:
        rows = []

    # Bucket by year-month of signup
    cohorts: dict[str, dict[str, int]] = {}
    for r in rows:
        ts = r.get("subscribed_at")
        if not ts:
            continue
        # Cope with both datetime objects (postgres) and ISO strings (sqlite)
        try:
            if isinstance(ts, str):
                month = ts[:7]  # YYYY-MM
            else:
                month = ts.strftime("%Y-%m")
        except Exception:
            continue
        bucket = cohorts.setdefault(
            month, {"signups": 0, "active": 0, "unsubscribed": 0}
        )
        bucket["signups"] += 1
        if r.get("status") == "active":
            bucket["active"] += 1
        elif r.get("status") == "unsubscribed":
            bucket["unsubscribed"] += 1

    # Sources distribution
    sources: dict[str, int] = {}
    for r in rows:
        src = r.get("source_channel") or "(unknown)"
        sources[src] = sources.get(src, 0) + 1

    conn.close()

    # Build sorted cohort list with retention rate
    cohort_list = []
    for month in sorted(cohorts.keys(), reverse=True):
        c = cohorts[month]
        signups = c["signups"]
        retention = round(c["active"] / signups * 100, 1) if signups else 0.0
        cohort_list.append({
            "month": month,
            "signups": signups,
            "active": c["active"],
            "unsubscribed": c["unsubscribed"],
            "retention_pct": retention,
        })

    return JSONResponse({
        "filter_source": source or None,
        "cohorts": cohort_list,
        "sources": sorted(
            [{"source": k, "count": v} for k, v in sources.items()],
            key=lambda x: -x["count"],
        ),
        "total_subscribers": sum(c["signups"] for c in cohort_list),
    })


@router.get("/sections-heatmap")
async def section_engagement_heatmap(request: Request):
    """Per-section engagement heatmap.

    Returns aggregate sends, opens, clicks per section across the last
    30 days, sorted by click rate. Highlights which sections drive
    engagement and which drag it down.
    """
    repo = get_repo()
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn = repo._conn()
    rows: list[dict] = []
    try:
        # section_engagement_scores is the materialised aggregate; fall back
        # to live event counting if the score table is empty.
        score_rows = conn.execute(
            "SELECT section_slug, sends, opens, clicks "
            "FROM section_engagement_scores ORDER BY clicks DESC LIMIT 100"
        ).fetchall()
        rows = [dict(r) for r in score_rows]
    except Exception:
        try:
            ev_rows = conn.execute(
                "SELECT section_slug, event_type, COUNT(*) as n "
                "FROM section_engagement_events WHERE occurred_at >= ? "
                "GROUP BY section_slug, event_type",
                (cutoff,),
            ).fetchall()
            buckets: dict[str, dict[str, int]] = {}
            for r in ev_rows:
                rd = dict(r)
                slug = rd["section_slug"]
                b = buckets.setdefault(slug, {"sends": 0, "opens": 0, "clicks": 0})
                et = rd["event_type"]
                if et in b:
                    b[et] += int(rd["n"] or 0)
            rows = [{"section_slug": k, **v} for k, v in buckets.items()]
        except Exception:
            rows = []
    conn.close()

    # Compute click + open rates per section
    sections = []
    for r in rows:
        sends = max(int(r.get("sends") or 0), 1)
        opens = int(r.get("opens") or 0)
        clicks = int(r.get("clicks") or 0)
        sections.append({
            "section_slug": r.get("section_slug"),
            "sends": sends,
            "opens": opens,
            "clicks": clicks,
            "open_rate_pct": round(opens / sends * 100, 1),
            "click_rate_pct": round(clicks / sends * 100, 1),
        })
    sections.sort(key=lambda s: -s["click_rate_pct"])
    return JSONResponse({
        "window_days": 30,
        "section_count": len(sections),
        "sections": sections,
    })

@router.get("/", response_class=HTMLResponse)
async def analytics_hub(request: Request):
    repo = get_repo()
    config = get_config()
    from weeklyamp.content.analytics_tools import calculate_nps, generate_content_report, forecast_revenue
    nps = calculate_nps(repo)
    content_report = generate_content_report(repo)
    forecasts = forecast_revenue(repo, months=12)
    return HTMLResponse(render("analytics_hub.html",
        nps=nps, content_report=content_report, forecasts=forecasts, config=config))

@router.get("/media-kit", response_class=HTMLResponse)
async def media_kit_download(request: Request):
    repo = get_repo()
    config = get_config()
    from weeklyamp.content.analytics_tools import generate_media_kit_text
    kit_text = generate_media_kit_text(repo, config)
    subscriber_count = repo.get_subscriber_count()
    summary = repo.get_revenue_summary()

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>TrueFans DISPATCH — Media Kit</title>
<style>
body {{ font-family: 'Inter', -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 24px; color: #1a1a2e; line-height: 1.7; }}
h1 {{ color: #e8645a; font-size: 28px; border-bottom: 3px solid #e8645a; padding-bottom: 12px; }}
h2 {{ color: #1a1a2e; font-size: 20px; margin-top: 32px; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 24px 0; }}
.stat-box {{ background: #f8f9fa; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; text-align: center; }}
.stat-box .number {{ font-size: 32px; font-weight: 900; color: #e8645a; }}
.stat-box .label {{ font-size: 13px; color: #6b7280; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; font-size: 14px; }}
th {{ background: #f8f9fa; font-weight: 600; }}
.footer {{ margin-top: 40px; padding-top: 20px; border-top: 2px solid #e5e7eb; font-size: 13px; color: #6b7280; }}
</style></head><body>
<h1>TrueFans DISPATCH — Media Kit</h1>
<p><strong>{config.newsletter.name}</strong> — {config.newsletter.tagline}</p>

<div class="stat-grid">
<div class="stat-box"><div class="number">{subscriber_count:,}</div><div class="label">Total Subscribers</div></div>
<div class="stat-box"><div class="number">3</div><div class="label">Newsletter Editions</div></div>
<div class="stat-box"><div class="number">9</div><div class="label">Issues per Week</div></div>
</div>

<h2>Our Editions</h2>
<table>
<tr><th>Edition</th><th>Audience</th><th>Content Focus</th></tr>
<tr><td><strong>Fan Edition</strong></td><td>Music fans, concert-goers</td><td>Artist spotlights, new releases, playlists, trivia, live music</td></tr>
<tr><td><strong>Artist Edition</strong></td><td>Independent musicians, songwriters</td><td>Career strategy, marketing, production, industry intelligence</td></tr>
<tr><td><strong>Industry Edition</strong></td><td>Labels, managers, publishers, distributors</td><td>Market analysis, deal flow, streaming data, business strategy</td></tr>
</table>

<h2>Sponsor Rates</h2>
<table>
<tr><th>Position</th><th>CPM</th><th>Per Issue (1K subs)</th><th>Notes</th></tr>
<tr><td>Top Banner</td><td>$45</td><td>$45</td><td>Premium placement, highest visibility</td></tr>
<tr><td>Mid-Content</td><td>$30</td><td>$30</td><td>Embedded between sections</td></tr>
<tr><td>Bottom</td><td>$21</td><td>$21</td><td>End-of-newsletter placement</td></tr>
</table>
<p><em>Volume discounts: 10% off weekly bookings, 20% off monthly commitments.</em></p>

<h2>Audience Demographics</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Primary Age Range</td><td>25-45</td></tr>
<tr><td>Music Industry Professionals</td><td>~35%</td></tr>
<tr><td>Independent Artists</td><td>~40%</td></tr>
<tr><td>Music Fans / Enthusiasts</td><td>~25%</td></tr>
<tr><td>Geographic Focus</td><td>US (65%), UK (12%), Canada (8%), Other (15%)</td></tr>
</table>

<h2>Why Advertise With Us</h2>
<ul>
<li>Highly engaged, niche audience — music professionals and passionate fans</li>
<li>3x weekly touchpoints across 3 targeted editions</li>
<li>AI-powered content ensures consistent quality and engagement</li>
<li>Full open/click tracking and reporting</li>
<li>Sponsor creative support available</li>
</ul>

<h2>Contact</h2>
<p>Email: <strong>sponsors@truefansnewsletters.com</strong><br>
Website: <strong>{config.site_domain}</strong></p>

<div class="footer">
<p>Generated on {__import__('datetime').datetime.utcnow().strftime('%B %d, %Y')} | {config.newsletter.name}</p>
</div>
</body></html>"""

    return HTMLResponse(html)
