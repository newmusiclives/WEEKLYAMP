"""Tests for the contributor stats aggregation.

Covers `Repository.get_contributor_stats`, which feeds the
/submissions/contributors editorial leaderboard.

Asserts:
  1. Returns empty list when there are no submissions
  2. Aggregates total/approved/published/rejected per email
  3. Excludes anonymous (empty-email) submissions
  4. Sets `trusted` only when >= 3 approved AND 0 rejected
  5. Computes approval_rate correctly
  6. Orders by published desc, then approved, then total
"""

from __future__ import annotations

import pytest


def _make_submission(repo, email: str, state: str = "submitted", name: str = "") -> int:
    """Insert a minimal valid submission row and set its review_state.

    artist_name is NOT NULL so we always supply one. Defaulting it to
    the email lets each test focus on the stats logic without restating
    the boilerplate."""
    conn = repo._conn()
    cur = conn.execute(
        "INSERT INTO artist_submissions (artist_name, artist_email) VALUES (?, ?)",
        (name or email or "Anonymous", email),
    )
    sub_id = cur.lastrowid
    conn.commit()
    conn.close()
    if state != "submitted":
        repo.update_submission_state(sub_id, state)
    return sub_id


def test_empty_when_no_submissions(repo):
    assert repo.get_contributor_stats() == []


def test_aggregates_per_email(repo):
    _make_submission(repo, "a@example.com", state="approved")
    _make_submission(repo, "a@example.com", state="published")
    _make_submission(repo, "a@example.com", state="rejected")

    stats = repo.get_contributor_stats()
    assert len(stats) == 1
    s = stats[0]
    assert s["email"] == "a@example.com"
    assert s["total"] == 3
    # 'approved' counts approved + scheduled + published per the SQL definition
    assert s["approved"] == 2
    assert s["published"] == 1
    assert s["rejected"] == 1


def test_excludes_anonymous_submitters(repo):
    """Submissions with empty artist_email cannot accrue stats — they
    are excluded from the aggregate so the leaderboard stays meaningful."""
    _make_submission(repo, "", name="Anon", state="published")
    _make_submission(repo, "named@example.com", state="published")

    stats = repo.get_contributor_stats()
    assert len(stats) == 1
    assert stats[0]["email"] == "named@example.com"


def test_trusted_requires_three_approved_and_zero_rejected(repo):
    """The trusted flag is conservative — 3 approved + 0 rejected. A
    single rejection disqualifies, even with many approvals."""
    # Contributor A: 3 approved, 0 rejected → trusted
    for _ in range(3):
        _make_submission(repo, "trusted@example.com", state="approved")
    # Contributor B: 5 approved + 1 rejected → not trusted
    for _ in range(5):
        _make_submission(repo, "tarnished@example.com", state="approved")
    _make_submission(repo, "tarnished@example.com", state="rejected")
    # Contributor C: 2 approved, 0 rejected → not trusted (under threshold)
    for _ in range(2):
        _make_submission(repo, "newbie@example.com", state="approved")

    stats = {s["email"]: s for s in repo.get_contributor_stats()}
    assert stats["trusted@example.com"]["trusted"] is True
    assert stats["tarnished@example.com"]["trusted"] is False
    assert stats["newbie@example.com"]["trusted"] is False


def test_approval_rate(repo):
    _make_submission(repo, "x@example.com", state="approved")
    _make_submission(repo, "x@example.com", state="rejected")
    _make_submission(repo, "x@example.com", state="approved")
    _make_submission(repo, "x@example.com", state="rejected")

    stats = repo.get_contributor_stats()
    assert stats[0]["approval_rate"] == 0.5


def test_orders_by_published_then_approved_then_total(repo):
    """The leaderboard's ordering is the value prop — most-published
    first. Ties break on approved count, then total volume."""
    # heaviest_publisher: 1 published, 0 other → top by published
    _make_submission(repo, "heaviest_publisher@example.com", state="published")

    # heaviest_approved: 0 published, 5 approved → second by approved
    for _ in range(5):
        _make_submission(repo, "heaviest_approved@example.com", state="approved")

    # heaviest_total: 0 published, 0 approved, 10 submitted → third by total
    for _ in range(10):
        _make_submission(repo, "heaviest_total@example.com", state="submitted")

    stats = repo.get_contributor_stats()
    emails = [s["email"] for s in stats]
    assert emails == [
        "heaviest_publisher@example.com",
        "heaviest_approved@example.com",
        "heaviest_total@example.com",
    ]
