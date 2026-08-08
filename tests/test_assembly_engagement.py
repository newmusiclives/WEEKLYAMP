"""Tests for poll / trivia injection into assembled newsletters.

TriviaManager could create polls, record votes, and render email-safe HTML,
but nothing in assembly.py ever called it — so a poll created for an issue
never actually reached the newsletter. These cover the wiring, and the
ordering contract with sponsor blocks: ads bracket the issue at
top/mid/bottom, engagement units sit inside that frame.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


def _assemble(repo, config, issue_id):
    with patch("weeklyamp.content.assembly._generate_welcome_intro", return_value="Welcome!"):
        with patch("weeklyamp.content.assembly._generate_ps_closing", return_value="Thanks!"):
            from weeklyamp.content.assembly import assemble_newsletter
            return assemble_newsletter(repo, issue_id, config)


@pytest.fixture()
def issue_with_sections(repo):
    """An issue with enough approved sections to exercise placement."""
    issue_id = repo.create_issue_with_schedule(
        issue_number=300, week_id="2026-W32", send_day="monday", edition_slug="fan"
    )
    for slug in ("backstage_pass", "vinyl_vault", "new_releases"):
        draft_id = repo.create_draft(issue_id, slug, f"Body copy for {slug}.", ai_model="test")
        repo.update_draft_status(draft_id, "approved")
    return issue_id


def _make_poll(repo, issue_id, question="Which era defined rock?"):
    return repo.create_trivia_poll(
        question_type="poll",
        question_text=question,
        options_json=json.dumps(["The 70s", "The 90s"]),
        correct_option_index=-1,
        explanation="",
        target_issue_id=issue_id,
        edition_slug="fan",
    )


def _make_trivia(repo, issue_id, question="Who produced Rumours?"):
    return repo.create_trivia_poll(
        question_type="trivia",
        question_text=question,
        options_json=json.dumps(["Ken Caillat", "Quincy Jones"]),
        correct_option_index=0,
        explanation="Caillat co-produced it.",
        target_issue_id=issue_id,
        edition_slug="fan",
    )


def test_poll_and_trivia_are_embedded(repo, issue_with_sections):
    from weeklyamp.core.config import load_config

    config = load_config()
    config.trivia_polls.enabled = True
    _make_poll(repo, issue_with_sections)
    _make_trivia(repo, issue_with_sections)

    html, plain = _assemble(repo, config, issue_with_sections)

    assert "Which era defined rock?" in html
    assert "Who produced Rumours?" in html
    assert "Have your say!" in html, "poll header"
    assert "Test your music knowledge!" in html, "trivia header"


def test_plain_text_enumerates_options(repo, issue_with_sections):
    from weeklyamp.core.config import load_config

    config = load_config()
    config.trivia_polls.enabled = True
    _make_poll(repo, issue_with_sections)

    _, plain = _assemble(repo, config, issue_with_sections)

    assert "POLL: Which era defined rock?" in plain
    assert "1. The 70s" in plain
    assert "2. The 90s" in plain


def test_disabled_config_renders_nothing(repo, issue_with_sections):
    """A disabled flag must suppress engagement even when rows exist."""
    from weeklyamp.core.config import load_config

    config = load_config()
    config.trivia_polls.enabled = False
    _make_poll(repo, issue_with_sections)
    _make_trivia(repo, issue_with_sections)

    html, plain = _assemble(repo, config, issue_with_sections)

    assert "Which era defined rock?" not in html
    assert "Who produced Rumours?" not in html
    assert "POLL:" not in plain


def test_closed_polls_are_skipped(repo, issue_with_sections):
    from weeklyamp.core.config import load_config

    config = load_config()
    config.trivia_polls.enabled = True
    poll_id = _make_poll(repo, issue_with_sections)
    repo.update_trivia_poll(poll_id, status="closed")

    html, _ = _assemble(repo, config, issue_with_sections)

    assert "Which era defined rock?" not in html


def test_assembly_survives_a_broken_trivia_lookup(repo, issue_with_sections):
    """Engagement is a nice-to-have; it must never break the send."""
    from weeklyamp.core.config import load_config

    config = load_config()
    config.trivia_polls.enabled = True

    with patch.object(
        type(repo), "get_trivia_for_issue", side_effect=RuntimeError("db exploded")
    ):
        html, _ = _assemble(repo, config, issue_with_sections)

    assert "backstage" in html.lower(), "the newsletter still assembled"


def test_ads_bracket_the_engagement_blocks(repo, issue_with_sections):
    """Top/bottom ads must stay outermost, with poll and trivia inside."""
    from weeklyamp.core.config import load_config

    config = load_config()
    config.trivia_polls.enabled = True
    _make_poll(repo, issue_with_sections)
    _make_trivia(repo, issue_with_sections)
    for position in ("top", "mid", "bottom"):
        repo.create_sponsor_block(
            issue_id=issue_with_sections,
            position=position,
            sponsor_name=f"{position.title()} Sponsor",
            headline=f"{position.upper()}-AD-MARKER",
            cta_url="https://example.com",
        )

    html, _ = _assemble(repo, config, issue_with_sections)

    top_ad = html.index("TOP-AD-MARKER")
    bottom_ad = html.index("BOTTOM-AD-MARKER")
    poll_at = html.index("Which era defined rock?")
    trivia_at = html.index("Who produced Rumours?")

    assert top_ad < poll_at < bottom_ad
    assert top_ad < trivia_at < bottom_ad
    assert poll_at < trivia_at, "poll runs early, trivia rewards finishing"
