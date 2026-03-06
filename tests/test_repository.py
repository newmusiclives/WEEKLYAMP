"""Tests for Repository CRUD operations."""

from __future__ import annotations

import pytest

from weeklyamp.core.database import DEFAULT_EDITIONS, DEFAULT_SECTIONS
from weeklyamp.db.repository import Repository


# ---- Issues ----

def test_create_issue_and_get_current(repo: Repository):
    issue_id = repo.create_issue(1, title="First Issue")
    assert isinstance(issue_id, int)

    current = repo.get_current_issue()
    assert current is not None
    assert current["issue_number"] == 1
    assert current["title"] == "First Issue"


def test_create_multiple_issues_returns_latest(repo: Repository):
    repo.create_issue(1, title="First")
    repo.create_issue(2, title="Second")
    current = repo.get_current_issue()
    assert current["issue_number"] == 2
    assert current["title"] == "Second"


# ---- Drafts ----

def test_create_draft_and_get_drafts_for_issue(repo: Repository):
    issue_id = repo.create_issue(1)
    draft_id = repo.create_draft(issue_id, "backstage_pass", "Draft content")
    assert isinstance(draft_id, int)

    drafts = repo.get_drafts_for_issue(issue_id)
    assert len(drafts) == 1
    assert drafts[0]["section_slug"] == "backstage_pass"
    assert drafts[0]["content"] == "Draft content"
    assert drafts[0]["version"] == 1


def test_create_draft_increments_version(repo: Repository):
    issue_id = repo.create_issue(1)
    repo.create_draft(issue_id, "backstage_pass", "v1")
    repo.create_draft(issue_id, "backstage_pass", "v2")

    # get_drafts_for_issue returns only the latest version per section
    drafts = repo.get_drafts_for_issue(issue_id)
    assert len(drafts) == 1
    assert drafts[0]["version"] == 2
    assert drafts[0]["content"] == "v2"


# ---- Section definitions ----

def test_get_active_sections_returns_seeded(repo: Repository):
    sections = repo.get_active_sections()
    assert len(sections) == len(DEFAULT_SECTIONS)
    slugs = {s["slug"] for s in sections}
    assert "backstage_pass" in slugs
    assert "ps_from_ps" in slugs


def test_get_active_sections_sorted_by_sort_order(repo: Repository):
    sections = repo.get_active_sections()
    orders = [s["sort_order"] for s in sections]
    assert orders == sorted(orders)


# ---- Editions ----

def test_get_editions_returns_seeded(repo: Repository):
    editions = repo.get_editions()
    assert len(editions) == len(DEFAULT_EDITIONS)
    slugs = {e["slug"] for e in editions}
    assert "fan" in slugs
    assert "artist" in slugs
    assert "industry" in slugs


def test_get_editions_sorted_by_sort_order(repo: Repository):
    editions = repo.get_editions()
    orders = [e["sort_order"] for e in editions]
    assert orders == sorted(orders)


# ---- Subscribe to editions ----

def test_subscribe_to_editions_creates_subscriber_and_links(repo: Repository):
    sub_id = repo.subscribe_to_editions(
        email="test@example.com",
        edition_slugs=["fan", "artist"],
        first_name="Tester",
        source_channel="website",
    )
    assert isinstance(sub_id, int)

    # Verify subscriber exists
    subs = repo.get_subscribers(status="active")
    emails = [s["email"] for s in subs]
    assert "test@example.com" in emails

    # Verify edition links via subscriber_editions table
    from weeklyamp.core.database import get_connection
    conn = get_connection(repo.db_path)
    rows = conn.execute(
        "SELECT * FROM subscriber_editions WHERE subscriber_id = ?", (sub_id,)
    ).fetchall()
    conn.close()
    assert len(rows) == 2


def test_subscribe_to_editions_with_custom_days(repo: Repository):
    sub_id = repo.subscribe_to_editions(
        email="days@example.com",
        edition_slugs=["fan"],
        edition_days={"fan": ["monday", "saturday"]},
    )
    from weeklyamp.core.database import get_connection
    conn = get_connection(repo.db_path)
    row = conn.execute(
        "SELECT send_days FROM subscriber_editions WHERE subscriber_id = ?", (sub_id,)
    ).fetchone()
    conn.close()
    assert row["send_days"] == "monday,saturday"


# ---- Table counts ----

def test_get_table_counts_returns_correct_structure(repo: Repository):
    counts = repo.get_table_counts()
    assert isinstance(counts, dict)
    expected_keys = {
        "issues", "section_definitions", "sources", "raw_content",
        "editorial_inputs", "drafts", "assembled_issues", "subscribers",
    }
    assert set(counts.keys()) == expected_keys
    # section_definitions should reflect seeded data
    assert counts["section_definitions"] == len(DEFAULT_SECTIONS)


# ---- Column validation ----

def test_validate_columns_rejects_bad_column_names():
    with pytest.raises(ValueError, match="Invalid columns"):
        Repository._validate_columns(
            "section_definitions",
            {"display_name": "ok", "DROP TABLE issues--": "evil"},
        )


def test_validate_columns_accepts_valid_columns():
    # Should not raise
    Repository._validate_columns(
        "section_definitions",
        {"display_name": "Test", "sort_order": 5},
    )


def test_validate_columns_rejects_unknown_table():
    with pytest.raises(ValueError, match="Invalid columns"):
        Repository._validate_columns(
            "nonexistent_table",
            {"anything": "value"},
        )
