"""The public media kit must never publish unmeasured engagement rates.

/advertise renders a media kit to prospective advertisers, including "Avg
Open Rate" and "Avg Click Rate". Those were hardcoded to 45% and 8% —
placeholders that would have been published as fact to people deciding
whether to buy ad space, on a newsletter that had never sent an issue.

Rates now come from engagement_metrics and are None until something has
actually been sent; the template omits the tile rather than showing a
number.
"""

from __future__ import annotations

import pytest

from weeklyamp.content.sponsor_rates import RateCardEngine


def _engine(repo):
    from weeklyamp.core.config import load_config

    return RateCardEngine(repo, load_config().sponsor_portal)


def _issue(repo, number: int):
    return repo.create_issue_with_schedule(
        issue_number=number, week_id="2026-W33", send_day="monday", edition_slug="fan"
    )


def test_no_sends_means_no_rates(repo):
    assert repo.get_average_engagement() is None


def test_media_kit_omits_rates_before_the_first_send(repo):
    media_kit = _engine(repo).get_media_kit_data()

    assert media_kit["avg_open_rate"] is None
    assert media_kit["avg_click_rate"] is None
    assert media_kit["issues_measured"] == 0


def test_rates_are_computed_from_real_sends(repo):
    issue_id = _issue(repo, 400)
    repo.save_engagement(issue_id, "campaign-1", sends=1000, opens=300, clicks=50)

    measured = repo.get_average_engagement()

    assert measured["avg_open_rate"] == 30.0
    assert measured["avg_click_rate"] == 5.0
    assert measured["issues_measured"] == 1


def test_rates_aggregate_across_sends_not_per_issue(repo):
    """A tiny issue must not swing the headline number.

    Averaging per-issue rates would give (50 + 10) / 2 = 30%. Aggregating
    over sends gives 60/1010 ≈ 5.9%, which is what an advertiser is buying.
    """
    big = _issue(repo, 401)
    small = _issue(repo, 402)
    repo.save_engagement(big, "c1", sends=1000, opens=50, clicks=10)
    repo.save_engagement(small, "c2", sends=10, opens=5, clicks=1)

    measured = repo.get_average_engagement()

    assert measured["avg_open_rate"] == pytest.approx(5.4, abs=0.1)
    assert measured["issues_measured"] == 2


def test_zero_send_rows_are_ignored(repo):
    """A queued-but-unsent issue must not count as a measured send."""
    issue_id = _issue(repo, 403)
    repo.save_engagement(issue_id, "c-empty", sends=0, opens=0, clicks=0)

    assert repo.get_average_engagement() is None


def test_media_kit_reports_measured_rates_once_available(repo):
    issue_id = _issue(repo, 404)
    repo.save_engagement(issue_id, "c1", sends=500, opens=200, clicks=25)

    media_kit = _engine(repo).get_media_kit_data()

    assert media_kit["avg_open_rate"] == 40.0
    assert media_kit["avg_click_rate"] == 5.0
    assert media_kit["issues_measured"] == 1
