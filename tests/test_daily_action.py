"""Tests for TrueFans Single Daily Action.

The AI rewrite is switched off in most of these (``ai_rewrite = False``)
so the pipeline is exercised without hitting a provider. The one test
that does cover the rewrite path stubs the generator instead.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from weeklyamp.content import daily_action as da


@pytest.fixture()
def da_repo(tmp_path):
    """Repository with schema + the daily action bank seeded."""
    from weeklyamp.core.database import init_database, seed_daily_actions, seed_editions
    from weeklyamp.db.repository import Repository

    db_file = str(tmp_path / "da.db")
    init_database(db_file)
    seed_editions(db_file)
    seed_daily_actions(db_file)
    return Repository(db_file)


@pytest.fixture()
def da_config():
    from weeklyamp.core.config import load_config

    cfg = load_config()
    cfg.daily_action.enabled = True
    cfg.daily_action.ai_rewrite = False
    return cfg


# ---- Pillar rotation ----

def test_pillar_is_fixed_per_weekday():
    # 2026-08-10 is a Monday; the cycle must hold across the week.
    assert da.pillar_for_date(date(2026, 8, 10)) == "capture"
    assert da.pillar_for_date(date(2026, 8, 11)) == "connect"
    assert da.pillar_for_date(date(2026, 8, 16)) == "sustain"


def test_same_weekday_next_week_keeps_pillar():
    assert da.pillar_for_date(date(2026, 8, 10)) == da.pillar_for_date(date(2026, 8, 17))


def test_every_pillar_has_a_seeded_bank(da_repo):
    for slug in da.PILLARS:
        assert da.pick_action(da_repo, slug) is not None, f"no actions for {slug}"


def test_should_send_on_respects_config(da_config):
    cfg = da_config.daily_action
    assert da.should_send_on(date(2026, 8, 10), cfg) is True     # Monday
    assert da.should_send_on(date(2026, 8, 15), cfg) is False    # Saturday


# ---- Build ----

def test_build_creates_draft_awaiting_approval(da_repo, da_config):
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert issue is not None
    assert issue["status"] == "draft"
    assert issue["pillar"] == "capture"
    assert issue["action_text"]
    assert issue["html_content"]


def test_build_is_idempotent_for_a_date(da_repo, da_config):
    first = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    second = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert first["id"] == second["id"]
    assert first["library_id"] == second["library_id"]


def test_rotation_does_not_repeat_an_action(da_repo, da_config):
    """Seven consecutive Mondays must draw seven different actions."""
    seen = set()
    for week in range(7):
        d = date(2026, 8, 10) + timedelta(weeks=week)
        issue = da.build_daily_action(da_repo, da_config, d)
        seen.add(issue["library_id"])
    assert len(seen) == 7


def test_build_skips_when_bank_is_empty(da_repo, da_config):
    conn = da_repo._conn()
    conn.execute("UPDATE daily_action_library SET is_active = 0")
    conn.commit()
    conn.close()
    assert da.build_daily_action(da_repo, da_config, date(2026, 8, 10)) is None


def test_autonomous_mode_skips_approval(da_repo, da_config):
    da_config.daily_action.require_approval = False
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert issue["status"] == "approved"


# ---- Rendered email ----

def test_email_carries_done_link_and_unsubscribe_token(da_repo, da_config):
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    html = issue["html_content"]
    assert f"/daily/done/{issue['id']}" in html
    # Left literal for SMTPSender to swap per recipient.
    assert "{{ unsubscribe_url }}" in html


def test_plain_text_alternative_is_populated(da_repo, da_config):
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert "TODAY'S ACTION" in issue["text_content"]
    assert issue["action_text"][:30] in issue["text_content"]


# ---- AI rewrite path ----

def test_ai_rewrite_replaces_copy(da_repo, da_config, monkeypatch):
    da_config.daily_action.ai_rewrite = True
    reply = (
        "SUBJECT: Fix your links today\n"
        "HOOK: Every bio you own is either a door or a dead end.\n"
        "ACTION: Open each profile and repoint the link at your signup page.\n"
        "WHY: An email address survives a platform you do not control.\n"
    )
    monkeypatch.setattr(
        "weeklyamp.content.generator.generate_draft_with_usage",
        lambda *a, **k: (reply, "test-model", 420),
    )
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert issue["subject"] == "Fix your links today"
    assert issue["action_text"].startswith("Open each profile")
    assert issue["generated_by"] == "test-model"
    assert issue["tokens_used"] == 420


def test_ai_failure_falls_back_to_library_copy(da_repo, da_config, monkeypatch):
    """A provider outage must still produce a correct, sendable email."""
    da_config.daily_action.ai_rewrite = True

    def _boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "weeklyamp.content.generator.generate_draft_with_usage", _boom
    )
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert issue is not None
    assert issue["generated_by"] == "library"
    assert issue["action_text"]


def test_ai_reply_without_action_line_is_rejected(da_repo, da_config, monkeypatch):
    da_config.daily_action.ai_rewrite = True
    monkeypatch.setattr(
        "weeklyamp.content.generator.generate_draft_with_usage",
        lambda *a, **k: ("SUBJECT: nice words\nHOOK: no action here\n", "m", 10),
    )
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert issue["generated_by"] == "library"


# ---- Completions and streaks ----

def test_completion_is_recorded_once_per_subscriber(da_repo, da_config):
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert da.mark_done(da_repo, issue["id"], 7, "2026-08-10") is True
    assert da.mark_done(da_repo, issue["id"], 7, "2026-08-10") is False
    assert da.completion_count(da_repo, issue["id"]) == 1


def test_streak_counts_consecutive_days(da_repo, da_config):
    for day in (8, 9, 10):
        issue = da.build_daily_action(da_repo, da_config, date(2026, 8, day))
        da.mark_done(da_repo, issue["id"], 7, f"2026-08-{day:02d}")
    assert da.streak_for_subscriber(da_repo, 7, date(2026, 8, 10)) == 3


def test_streak_breaks_on_a_missed_day(da_repo, da_config):
    for day in (8, 10):
        issue = da.build_daily_action(da_repo, da_config, date(2026, 8, day))
        da.mark_done(da_repo, issue["id"], 7, f"2026-08-{day:02d}")
    # The 9th was missed, so only the 10th counts.
    assert da.streak_for_subscriber(da_repo, 7, date(2026, 8, 10)) == 1


def test_streak_is_zero_for_unknown_subscriber(da_repo):
    assert da.streak_for_subscriber(da_repo, 0, date(2026, 8, 10)) == 0


# ---- Send guards ----

def test_send_refuses_when_disabled(da_repo, da_config):
    da_config.daily_action.enabled = False
    result = da.send_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert result["sent"] == 0
    assert "disabled" in result["skipped"]


def test_send_refuses_unapproved_draft(da_repo, da_config):
    da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    result = da.send_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert result["sent"] == 0
    assert "draft" in result["skipped"]


def test_send_refuses_on_a_non_send_day(da_repo, da_config):
    result = da.send_daily_action(da_repo, da_config, date(2026, 8, 15))  # Saturday
    assert "not a send day" in result["skipped"]


def test_send_refuses_to_send_twice(da_repo, da_config):
    issue = da.build_daily_action(da_repo, da_config, date(2026, 8, 10))
    da.mark_sent(da_repo, issue["id"], 12)
    result = da.send_daily_action(da_repo, da_config, date(2026, 8, 10))
    assert result["skipped"] == "already sent"


# ---- Seeding ----

def test_seed_is_idempotent(tmp_path):
    from weeklyamp.core.database import init_database, seed_daily_actions

    db_file = str(tmp_path / "seed.db")
    init_database(db_file)
    first = seed_daily_actions(db_file)
    assert first > 0
    assert seed_daily_actions(db_file) == 0


# ---- Routes ----

@pytest.fixture()
def da_client(tmp_path, monkeypatch):
    """TestClient on a DB with the action bank seeded and auth disabled."""
    from starlette.testclient import TestClient

    from weeklyamp.core.database import init_database, seed_daily_actions, seed_editions
    from weeklyamp.web.app import create_app

    db_file = str(tmp_path / "routes.db")
    init_database(db_file)
    seed_editions(db_file)
    seed_daily_actions(db_file)

    monkeypatch.setenv("WEEKLYAMP_DB_PATH", db_file)
    monkeypatch.delenv("WEEKLYAMP_ADMIN_HASH", raising=False)
    monkeypatch.delenv("WEEKLYAMP_ADMIN_PASSWORD", raising=False)
    import weeklyamp.web.security as _sec
    _sec.invalidate_admin_hash_cache()

    return TestClient(create_app()), db_file


def test_done_route_records_completion(da_client, da_config):
    from weeklyamp.db.repository import Repository

    client, db_file = da_client
    repo = Repository(db_file)
    issue = da.build_daily_action(repo, da_config, date.today())

    response = client.get(f"/daily/done/{issue['id']}")
    assert response.status_code == 200
    assert da.completion_count(repo, issue["id"]) == 1


def test_done_route_404s_on_unknown_issue(da_client):
    client, _ = da_client
    assert client.get("/daily/done/424242").status_code == 404


def test_admin_page_renders(da_client):
    client, _ = da_client
    response = client.get("/admin/daily-action")
    assert response.status_code == 200
    assert "Single Daily Action" in response.text


def test_daily_routes_survive_the_coming_soon_gate(da_client, da_config, monkeypatch):
    """A link already sitting in an inbox must keep working while hidden."""
    from weeklyamp.db.repository import Repository

    client, db_file = da_client
    repo = Repository(db_file)
    issue = da.build_daily_action(repo, da_config, date.today())

    from weeklyamp.web.security import ComingSoonMiddleware
    gate = ComingSoonMiddleware(app=None, enabled=True)
    assert any(
        f"/daily/done/{issue['id']}".startswith(prefix + "/")
        for prefix in gate._ALWAYS_ALLOW
    )


def test_daily_action_edition_is_seeded(da_repo):
    edition = da_repo.get_edition_by_slug(da.EDITION_SLUG)
    assert edition is not None
    assert edition["is_active"] == 1
