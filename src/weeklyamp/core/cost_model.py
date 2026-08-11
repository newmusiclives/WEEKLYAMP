"""Shared cost model — used by both /admin/cost-dashboard and the
Revenue Dashboard so the P&L view and the per-edition view always
agree on the numbers.

Two things make this more than a single rate times a token count:

**Two model tiers.** Reader-facing prose is written by ``config.ai.model``;
the high-volume scoring passes (the editor's per-draft review) run on the
cheaper ``config.ai.review_model``. A single blended rate can't describe
both, so the per-tier rates are the inputs and the blend is derived from
the modeled call mix.

**Shared infrastructure.** Hosting and Postgres are one bill for the whole
platform, not one per location. Amortizing the full $25 against a single
location's issues overstates every location after the first, so the
divisor includes ``WEEKLYAMP_COST_LOCATIONS``.

Unit costs are env-overridable. Defaults track list prices as of
2026-08-11: Sonnet 5 at introductory $2/$10 per 1M (reverting to $3/$15
after 2026-08-31), Haiku 4.5 at $1/$5 per 1M, GHL/Mailgun $0.80/1k
delivery, Railway + Postgres $25/mo combined.

Everything here is *modeled* until real token telemetry exists. Once
issues have been produced, ``per_edition_costs`` switches those editions
to measured token counts — see the ``source`` field on each row.
"""

from __future__ import annotations

import os


CANONICAL_EDITIONS: tuple[str, ...] = ("fan", "artist", "industry")

# --- Modeled call mix for one issue -----------------------------------
# Calibrated against the one real assembly run (2026-08-08): 74 drafts
# averaging 2,247 characters, i.e. ~562 output tokens per section. Input
# is estimated from prompt construction (system prompt + section brief +
# verified-facts sheet), not measured — it is the least certain number
# here and should be replaced by telemetry when available.
WRITE_INPUT_TOKENS_PER_SECTION = 2000
WRITE_OUTPUT_TOKENS_PER_SECTION = 562

# The editor reviews every draft — one call per section, capped at 500
# output tokens, sending up to 2,000 characters of the draft back.
REVIEW_INPUT_TOKENS_PER_SECTION = 650
REVIEW_OUTPUT_TOKENS_PER_SECTION = 350

# Per-issue extras on the writing tier: subject lines, preheader, and the
# verified-facts audit pass.
EXTRA_INPUT_TOKENS_PER_ISSUE = 8000
EXTRA_OUTPUT_TOKENS_PER_ISSUE = 3000

# Used only when the section cap can't be read off the config.
DEFAULT_SECTIONS_PER_ISSUE = 15


def pricing() -> dict[str, float]:
    """Return current pricing assumptions.

    Re-read every call so env-var changes take effect without a
    restart — keeps this safe to call from multiple request handlers.
    """
    return {
        # Writing tier — Sonnet 5 list prices ($/million -> $/1k).
        "write_input_per_1k": float(os.environ.get("WEEKLYAMP_COST_WRITE_INPUT_PER_1K", "0.002")),
        "write_output_per_1k": float(os.environ.get("WEEKLYAMP_COST_WRITE_OUTPUT_PER_1K", "0.010")),
        # Review tier — Haiku 4.5 list prices.
        "review_input_per_1k": float(os.environ.get("WEEKLYAMP_COST_REVIEW_INPUT_PER_1K", "0.001")),
        "review_output_per_1k": float(os.environ.get("WEEKLYAMP_COST_REVIEW_OUTPUT_PER_1K", "0.005")),
        "email_per_1k": float(os.environ.get("WEEKLYAMP_COST_EMAIL_PER_1K", "0.80")),
        "hosting_monthly": float(os.environ.get("WEEKLYAMP_COST_HOSTING_MONTHLY", "20.00")),
        "db_monthly": float(os.environ.get("WEEKLYAMP_COST_DB_MONTHLY", "5.00")),
        # Locations sharing the infrastructure bill. One location = one
        # group of three editions.
        "locations": max(1.0, float(os.environ.get("WEEKLYAMP_COST_LOCATIONS", "1"))),
    }


def sections_per_issue(config) -> int:
    """How many sections one drafting run generates.

    Mirrors ``config.ai.max_sections_per_issue``; a cap of 0 means "draft
    the whole library", which we can't size without a DB read, so the
    modeled default stands in.
    """
    cap = getattr(getattr(config, "ai", None), "max_sections_per_issue", 0) or 0
    return cap if cap > 0 else DEFAULT_SECTIONS_PER_ISSUE


def modeled_issue_tokens(config) -> dict[str, int]:
    """Token counts for one modeled issue, split by tier."""
    n = sections_per_issue(config)
    return {
        "write_input": n * WRITE_INPUT_TOKENS_PER_SECTION + EXTRA_INPUT_TOKENS_PER_ISSUE,
        "write_output": n * WRITE_OUTPUT_TOKENS_PER_SECTION + EXTRA_OUTPUT_TOKENS_PER_ISSUE,
        "review_input": n * REVIEW_INPUT_TOKENS_PER_SECTION,
        "review_output": n * REVIEW_OUTPUT_TOKENS_PER_SECTION,
    }


def modeled_llm_cost_per_issue(config) -> float:
    """Modeled LLM cost for one issue, priced per tier.

    Tracks the section cap, so tightening ``max_sections_per_issue``
    shows up on the dashboard without anyone editing a constant.
    """
    p = pricing()
    t = modeled_issue_tokens(config)
    return (
        t["write_input"] / 1000.0 * p["write_input_per_1k"]
        + t["write_output"] / 1000.0 * p["write_output_per_1k"]
        + t["review_input"] / 1000.0 * p["review_input_per_1k"]
        + t["review_output"] / 1000.0 * p["review_output_per_1k"]
    )


def blended_per_1k(config) -> float:
    """Effective $/1k tokens across both tiers, for the modeled call mix.

    Telemetry records a single ``tokens_used`` total per call with no tier
    attribution, so measured editions have to be priced at one blended
    rate. This derives that rate from the modeled write/review mix rather
    than hardcoding it — if the mix shifts, the rate follows.

    An explicit ``WEEKLYAMP_COST_BLENDED_PER_1K`` still wins, so the rate
    can be pinned to a real invoice once one exists.
    """
    override = os.environ.get("WEEKLYAMP_COST_BLENDED_PER_1K", "").strip()
    if override:
        return float(override)
    t = modeled_issue_tokens(config)
    total = sum(t.values())
    if total <= 0:
        return 0.0
    return modeled_llm_cost_per_issue(config) / (total / 1000.0)


def issues_per_month(config) -> int:
    """Estimate issues-per-month from schedule × canonical edition count."""
    editions = len(CANONICAL_EDITIONS)
    sends_per_week = max(1, len(getattr(config.schedule, "send_days", []) or []))
    return max(1, editions * sends_per_week * 4)


def infra_per_issue(config) -> float:
    """Infrastructure cost amortized across every location's issues.

    Hosting and Postgres are one platform bill. Dividing it by a single
    location's issue count is right for the first location and wrong for
    every one after it.
    """
    p = pricing()
    denominator = issues_per_month(config) * p["locations"]
    if denominator <= 0:
        return 0.0
    return (p["hosting_monthly"] + p["db_monthly"]) / denominator


def per_edition_costs(repo, config) -> list[dict]:
    """Per-edition cost rows used by /admin/cost-dashboard.

    Fails defensively — if the repo query raises (e.g. schema drift),
    returns all-modeled rows rather than 500ing the caller.
    """
    p = pricing()
    try:
        stats = repo.get_cost_stats_by_edition(since_days=30)
        sub_counts = repo.get_subscriber_counts_by_edition()
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "per_edition_costs: telemetry query failed; falling back to modeled"
        )
        stats = []
        sub_counts = {}

    measured = {s["edition_slug"]: s for s in stats}
    infra = infra_per_issue(config)
    modeled_llm = modeled_llm_cost_per_issue(config)
    rate = blended_per_1k(config)

    rows: list[dict] = []
    for slug in CANONICAL_EDITIONS:
        m = measured.get(slug)
        if m and m.get("avg_tokens_per_issue", 0) > 0:
            llm_cost = m["avg_tokens_per_issue"] / 1000.0 * rate
            source = "measured"
            issue_count = m["issue_count"]
            avg_tokens = m["avg_tokens_per_issue"]
        else:
            llm_cost = modeled_llm
            source = "modeled"
            issue_count = m["issue_count"] if m else 0
            avg_tokens = 0
        subs = int(sub_counts.get(slug, 0) or 0)
        email_cost = subs / 1000.0 * p["email_per_1k"]
        rows.append({
            "slug": slug,
            "label": slug.capitalize(),
            "source": source,
            "issue_count": issue_count,
            "avg_tokens": avg_tokens,
            "llm_cost": llm_cost,
            "infra_cost": infra,
            "subscribers": subs,
            "email_cost": email_cost,
            "total": llm_cost + infra + email_cost,
        })
    return rows


def monthly_cost_estimate(repo, config) -> dict[str, float]:
    """Project the monthly cost of production + delivery.

    Composed as:
      llm_monthly     = issues_per_month × avg_llm_cost_per_edition
                        (measured when we have data, modeled otherwise)
      infra_monthly   = this location's share of (hosting + db)
      email_monthly   = issues_per_month × avg_subs_per_send × $0.80/1k
      total_monthly   = llm + infra + email

    All values returned in DOLLARS (float), keyed so the Revenue
    Dashboard can subtract them from revenue to compute net.
    """
    p = pricing()
    per_edition = per_edition_costs(repo, config)
    ipm = issues_per_month(config)

    # Average per-edition LLM cost — weight each edition equally since
    # our current schedule has the same frequency for all three.
    avg_llm_per_edition = (
        sum(r["llm_cost"] for r in per_edition) / len(per_edition)
        if per_edition else modeled_llm_cost_per_issue(config)
    )

    # Sum active subscribers across editions (a subscriber to two
    # editions is counted twice because they receive two sends).
    total_subscribers_reach = sum(r["subscribers"] for r in per_edition)

    llm_monthly = ipm * avg_llm_per_edition
    # This location's share of the platform bill, not the whole bill.
    infra_monthly = (p["hosting_monthly"] + p["db_monthly"]) / p["locations"]
    # Email: issues_per_month already = 3 editions × sends_per_week × 4
    # weeks, so multiplying by per-edition subscribers is wrong —
    # total_subscribers_reach is per-send, and issues_per_month is the
    # total sends across all editions. So: sends × avg_subs_per_send.
    avg_subs_per_send = (
        total_subscribers_reach / len(per_edition) if per_edition else 0
    )
    email_monthly = ipm * avg_subs_per_send / 1000.0 * p["email_per_1k"]

    total_monthly = llm_monthly + infra_monthly + email_monthly
    return {
        "llm_monthly": round(llm_monthly, 2),
        "infra_monthly": round(infra_monthly, 2),
        "email_monthly": round(email_monthly, 2),
        "total_monthly": round(total_monthly, 2),
        "issues_per_month": ipm,
        "total_subscribers_reach": total_subscribers_reach,
    }
