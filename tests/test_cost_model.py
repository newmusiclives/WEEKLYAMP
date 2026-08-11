"""Tests for the two-tier cost model.

The model has to hold three properties that the previous flat version
didn't:

  1. Cost tracks the section cap, so tightening ``max_sections_per_issue``
     shows up without anyone editing a constant.
  2. The two model tiers are priced separately — the review tier is
     cheaper, so shifting work onto it must lower the total.
  3. Infrastructure is one platform bill shared across locations, not one
     bill per location.
"""

from __future__ import annotations

import pytest

from weeklyamp.core import cost_model as cm
from weeklyamp.core.models import AIConfig, AppConfig, ScheduleConfig


def _config(cap: int = 15, sends: int = 3) -> AppConfig:
    return AppConfig(
        ai=AIConfig(max_sections_per_issue=cap),
        schedule=ScheduleConfig(send_days=["monday", "wednesday", "saturday"][:sends]),
    )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Cost env overrides must not leak between tests."""
    for key in list(os_environ_keys()):
        monkeypatch.delenv(key, raising=False)


def os_environ_keys():
    import os
    return [k for k in os.environ if k.startswith("WEEKLYAMP_COST_")]


# --- section cap drives cost ------------------------------------------


def test_cost_scales_with_section_cap():
    assert cm.modeled_llm_cost_per_issue(_config(30)) > cm.modeled_llm_cost_per_issue(_config(15))


def test_uncapped_config_falls_back_to_default_size():
    """cap=0 means 'whole library', which we can't size without a DB read."""
    assert cm.sections_per_issue(_config(0)) == cm.DEFAULT_SECTIONS_PER_ISSUE


def test_modeled_cost_is_in_the_expected_range():
    """15 sections across both tiers lands near $0.23 — sanity, not spec."""
    cost = cm.modeled_llm_cost_per_issue(_config(15))
    assert 0.15 < cost < 0.35, cost


# --- tier split --------------------------------------------------------


def test_review_tier_is_cheaper_than_write_tier():
    p = cm.pricing()
    assert p["review_input_per_1k"] < p["write_input_per_1k"]
    assert p["review_output_per_1k"] < p["write_output_per_1k"]


def test_blended_rate_sits_between_the_two_tiers():
    """A derived blend can't be cheaper than the cheap tier's input rate
    or dearer than the expensive tier's output rate."""
    p = cm.pricing()
    rate = cm.blended_per_1k(_config(15))
    assert p["review_input_per_1k"] <= rate <= p["write_output_per_1k"]


def test_blended_rate_respects_explicit_override(monkeypatch):
    monkeypatch.setenv("WEEKLYAMP_COST_BLENDED_PER_1K", "0.0999")
    assert cm.blended_per_1k(_config(15)) == pytest.approx(0.0999)


def test_raising_review_price_raises_total(monkeypatch):
    before = cm.modeled_llm_cost_per_issue(_config(15))
    monkeypatch.setenv("WEEKLYAMP_COST_REVIEW_OUTPUT_PER_1K", "0.500")
    assert cm.modeled_llm_cost_per_issue(_config(15)) > before


def test_blended_rate_reconciles_with_total_cost():
    """rate × total tokens must equal the per-tier sum, or the measured
    path and the modeled path would disagree."""
    config = _config(15)
    tokens = sum(cm.modeled_issue_tokens(config).values())
    implied = cm.blended_per_1k(config) * tokens / 1000.0
    assert implied == pytest.approx(cm.modeled_llm_cost_per_issue(config))


# --- shared infrastructure --------------------------------------------


def test_infra_is_shared_across_locations(monkeypatch):
    one = cm.infra_per_issue(_config())
    monkeypatch.setenv("WEEKLYAMP_COST_LOCATIONS", "4")
    four = cm.infra_per_issue(_config())
    assert four == pytest.approx(one / 4)


def test_locations_floor_at_one(monkeypatch):
    """A zero or negative location count must not divide by zero."""
    monkeypatch.setenv("WEEKLYAMP_COST_LOCATIONS", "0")
    assert cm.pricing()["locations"] == 1.0
    assert cm.infra_per_issue(_config()) > 0


def test_monthly_infra_is_this_locations_share(monkeypatch, repo):
    monkeypatch.setenv("WEEKLYAMP_COST_LOCATIONS", "5")
    costs = cm.monthly_cost_estimate(repo, _config())
    assert costs["infra_monthly"] == pytest.approx(25.0 / 5)


# --- rollup integrity --------------------------------------------------


def test_per_edition_rows_cover_every_canonical_edition(repo):
    rows = cm.per_edition_costs(repo, _config())
    assert [r["slug"] for r in rows] == list(cm.CANONICAL_EDITIONS)


def test_row_total_is_the_sum_of_its_parts(repo):
    for row in cm.per_edition_costs(repo, _config()):
        assert row["total"] == pytest.approx(
            row["llm_cost"] + row["infra_cost"] + row["email_cost"]
        )


def test_rows_are_modeled_without_telemetry(repo):
    """With an empty agent log every edition must say so, not imply measurement."""
    for row in cm.per_edition_costs(repo, _config()):
        assert row["source"] == "modeled"
        assert row["avg_tokens"] == 0


def test_monthly_total_is_the_sum_of_its_parts(repo):
    costs = cm.monthly_cost_estimate(repo, _config())
    assert costs["total_monthly"] == pytest.approx(
        costs["llm_monthly"] + costs["infra_monthly"] + costs["email_monthly"], abs=0.02
    )


def test_issues_per_month_tracks_schedule():
    assert cm.issues_per_month(_config(sends=3)) == 36
    assert cm.issues_per_month(_config(sends=1)) == 12
