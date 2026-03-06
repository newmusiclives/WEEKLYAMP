"""Tests for database initialisation, seeding, and migrations."""

from __future__ import annotations

import sqlite3

from weeklyamp.core.database import (
    DEFAULT_EDITIONS,
    DEFAULT_SECTIONS,
    get_connection,
    get_schema_version,
    init_database,
    seed_editions,
    seed_sections,
)
from weeklyamp.db.migrations import MIGRATIONS, get_current_version, run_migrations


# ---- Schema creation ----

EXPECTED_TABLES = {
    "schema_version",
    "issues",
    "section_definitions",
    "sources",
    "raw_content",
    "editorial_inputs",
    "drafts",
    "assembled_issues",
    "subscribers",
    "engagement_metrics",
    "section_rotation_log",
    "send_schedule",
    "sponsor_blocks",
    "sponsors",
    "sponsor_bookings",
    "ai_agents",
    "agent_tasks",
    "agent_output_log",
    "guest_contacts",
    "guest_articles",
    "artist_submissions",
    "editorial_calendar",
    "growth_metrics",
    "social_posts",
    "security_log",
    "newsletter_editions",
    "subscriber_editions",
}


def test_init_database_creates_all_tables(tmp_path):
    db = str(tmp_path / "init.db")
    init_database(db)

    conn = get_connection(db)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    conn.close()

    table_names = {r["name"] for r in rows}
    missing = EXPECTED_TABLES - table_names
    assert not missing, f"Missing tables after init_database: {missing}"


def test_init_database_is_idempotent(tmp_path):
    db = str(tmp_path / "idem.db")
    init_database(db)
    init_database(db)  # second call should not raise

    conn = get_connection(db)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    conn.close()
    assert len(rows) >= len(EXPECTED_TABLES)


# ---- Seed sections ----

def test_seed_sections_inserts_correct_count(tmp_path):
    db = str(tmp_path / "seed.db")
    init_database(db)
    count = seed_sections(db)
    assert count == len(DEFAULT_SECTIONS)


def test_seed_sections_is_idempotent(tmp_path):
    db = str(tmp_path / "idem_sec.db")
    init_database(db)
    seed_sections(db)
    second = seed_sections(db)
    assert second == 0, "Second seed should insert 0 new rows"

    conn = get_connection(db)
    row = conn.execute("SELECT COUNT(*) as c FROM section_definitions").fetchone()
    conn.close()
    assert row["c"] == len(DEFAULT_SECTIONS)


# ---- Seed editions ----

def test_seed_editions_inserts_correct_count(tmp_path):
    db = str(tmp_path / "ed.db")
    init_database(db)
    count = seed_editions(db)
    assert count == len(DEFAULT_EDITIONS)


def test_seed_editions_is_idempotent(tmp_path):
    db = str(tmp_path / "idem_ed.db")
    init_database(db)
    seed_editions(db)
    second = seed_editions(db)
    assert second == 0

    conn = get_connection(db)
    row = conn.execute("SELECT COUNT(*) as c FROM newsletter_editions").fetchone()
    conn.close()
    assert row["c"] == len(DEFAULT_EDITIONS)


# ---- Migrations ----

def test_migrations_run_in_order(tmp_path):
    db = str(tmp_path / "mig.db")
    init_database(db)
    # After init_database, all migrations should already be applied
    applied = run_migrations(db)
    assert applied == [], "All migrations should have been applied by init_database"

    conn = get_connection(db)
    version = get_current_version(conn)
    conn.close()
    assert version == max(MIGRATIONS.keys())


def test_migrations_are_idempotent(tmp_path):
    db = str(tmp_path / "mig_idem.db")
    init_database(db)
    # Running migrations again should apply nothing and not raise
    applied = run_migrations(db)
    assert applied == []


# ---- Schema version ----

def test_get_schema_version_returns_correct_value(tmp_path):
    db = str(tmp_path / "ver.db")
    init_database(db)
    version = get_schema_version(db)
    assert version == max(MIGRATIONS.keys())


def test_get_schema_version_returns_none_for_missing_db(tmp_path):
    db = str(tmp_path / "nonexistent.db")
    assert get_schema_version(db) is None
