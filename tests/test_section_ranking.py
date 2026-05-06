"""Tests for per-subscriber section ranking.

Covers GenreEngine.rank_sections_for_subscriber, which blends:
  - explicit genre prefs (subscriber_genres × section_genres)
  - implicit click engagement (subscriber_interest_profiles)

These are the two signals the personalization layer leans on. The tests
assert that:
  1. With the engine disabled, ordering is untouched.
  2. With genre prefs set and a matching section, that section bubbles up.
  3. With engagement scores, high-clicked sections rise.
  4. With both signals, the combined score wins (genre_weight controls).
  5. Sections with neither signal stay in their original relative order
     after the matched ones, not interleaved.
"""

from __future__ import annotations

import pytest

from weeklyamp.content.genre_engine import GenreEngine
from weeklyamp.core.models import GenrePreferencesConfig


@pytest.fixture()
def subscriber_id(repo):
    """Create a real subscriber row so FK-bound writes succeed."""
    repo.upsert_subscriber(email="ranker@example.com")
    conn = repo._conn()
    row = conn.execute(
        "SELECT id FROM subscribers WHERE email = ?", ("ranker@example.com",),
    ).fetchone()
    conn.close()
    return row["id"]


@pytest.fixture()
def sections():
    """A fixed list of sections in editorial order — matches the shape
    that callers (assembly.py) pass into the ranker."""
    return [
        {"slug": "backstage_pass", "sort_order": 10},
        {"slug": "industry_pulse", "sort_order": 11},
        {"slug": "stage_ready", "sort_order": 22},
        {"slug": "coaching", "sort_order": 20},
    ]


def _engine(repo, *, enabled: bool = True) -> GenreEngine:
    return GenreEngine(repo, GenrePreferencesConfig(enabled=enabled))


def test_disabled_engine_returns_original_order(repo, subscriber_id, sections):
    """The engine's enabled flag is the master switch — when off, no
    reordering happens regardless of what's in the prefs/engagement
    tables."""
    engine = _engine(repo, enabled=False)
    result = engine.rank_sections_for_subscriber(sections, subscriber_id)
    assert [s["slug"] for s in result] == [s["slug"] for s in sections]


def test_no_signals_returns_original_order(repo, subscriber_id, sections):
    """A subscriber with no genre prefs and no click history gets the
    editorial order unchanged — the ranker is purely additive."""
    engine = _engine(repo)
    result = engine.rank_sections_for_subscriber(sections, subscriber_id)
    assert [s["slug"] for s in result] == [s["slug"] for s in sections]


def test_genre_match_bubbles_section_up(repo, subscriber_id, sections):
    """Subscriber prefers Rock; stage_ready is tagged Rock; stage_ready
    should move from position 3 to position 1 in the output."""
    repo.set_subscriber_genres(subscriber_id, ["Rock"])
    repo.set_section_genres("stage_ready", ["Rock"])
    engine = _engine(repo)

    result = engine.rank_sections_for_subscriber(sections, subscriber_id)
    assert result[0]["slug"] == "stage_ready"
    # The other sections fall through in their original editorial order
    remaining = [s["slug"] for s in result[1:]]
    assert remaining == ["backstage_pass", "industry_pulse", "coaching"]


def test_engagement_score_alone_can_drive_ordering(repo, subscriber_id, sections):
    """With genre_weight=0 the ranker becomes pure engagement-history.
    A subscriber who has only clicked 'coaching' should see coaching
    surface to the top even with no genre prefs set."""
    conn = repo._conn()
    conn.execute(
        "INSERT INTO subscriber_interest_profiles (subscriber_id, section_slug, engagement_score) VALUES (?, ?, ?)",
        (subscriber_id, "coaching", 0.9),
    )
    conn.commit()
    conn.close()

    engine = _engine(repo)
    result = engine.rank_sections_for_subscriber(sections, subscriber_id, genre_weight=0.0)
    assert result[0]["slug"] == "coaching"


def test_genre_weight_controls_the_blend(repo, subscriber_id, sections):
    """The same subscriber has a genre signal (Rock → stage_ready) AND
    an engagement signal (coaching). With genre_weight=1.0 stage_ready
    wins; with genre_weight=0.0 coaching wins. This asserts the blend
    is actually being applied, not just one-or-the-other."""
    repo.set_subscriber_genres(subscriber_id, ["Rock"])
    repo.set_section_genres("stage_ready", ["Rock"])
    conn = repo._conn()
    conn.execute(
        "INSERT INTO subscriber_interest_profiles (subscriber_id, section_slug, engagement_score) VALUES (?, ?, ?)",
        (subscriber_id, "coaching", 0.9),
    )
    conn.commit()
    conn.close()

    engine = _engine(repo)

    pure_genre = engine.rank_sections_for_subscriber(sections, subscriber_id, genre_weight=1.0)
    pure_eng = engine.rank_sections_for_subscriber(sections, subscriber_id, genre_weight=0.0)
    assert pure_genre[0]["slug"] == "stage_ready"
    assert pure_eng[0]["slug"] == "coaching"
