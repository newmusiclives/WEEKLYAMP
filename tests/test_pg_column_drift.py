"""Regression tests for the Postgres column-drift bug that blocked the
first real publish on 2026-08-08.

Assembly failed in production with:

    column "preheader_text" of relation "assembled_issues" does not exist

even though the column is present in schema_pg.sql and a v48 migration adds
it. The cause is an ordering trap in init_pg_database():

  1. schema_pg.sql runs first. Its `CREATE TABLE IF NOT EXISTS
     assembled_issues` is a no-op because the table already existed from an
     earlier deploy, so the new column is never added...
  2. ...but the same file still stamps `INSERT INTO schema_version VALUES
     (48)` (and on up to 54).
  3. run_pg_migrations() then reads current=54 and skips PG_MIGRATIONS[48] —
     the ALTER TABLE that would have added the column.

The drift is therefore permanent: every restart re-stamps and re-skips.

The fix re-derives every ADD COLUMN from the migrations and applies the ones
the live schema is missing, so drift cannot outlive a boot.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from weeklyamp.db.migrations import (
    PG_COLUMN_REPAIRS,
    find_missing_pg_columns,
    run_pg_column_repairs,
)


def _fake_conn(columns: list[tuple[str, str]]) -> MagicMock:
    """A connection whose information_schema reports exactly `columns`."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"table_name": t, "column_name": c} for t, c in columns
    ]
    return conn


def test_preheader_text_is_covered():
    """The column from the production failure must be in the repair set."""
    assert ("assembled_issues", "preheader_text") in PG_COLUMN_REPAIRS


def test_repairs_are_idempotent():
    """Every statement must be safe to re-run on an already-correct schema."""
    for statement in PG_COLUMN_REPAIRS.values():
        assert "ADD COLUMN IF NOT EXISTS" in statement, statement


def test_missing_column_on_existing_table_is_detected():
    conn = _fake_conn([("assembled_issues", "id"), ("assembled_issues", "html_content")])

    missing = find_missing_pg_columns(conn)

    assert ("assembled_issues", "preheader_text") in missing


def test_present_column_is_not_reported_missing():
    conn = _fake_conn([("assembled_issues", "id"), ("assembled_issues", "preheader_text")])

    missing = find_missing_pg_columns(conn)

    assert ("assembled_issues", "preheader_text") not in missing


def test_absent_table_is_skipped_not_altered():
    """A missing table is a different failure; ALTERing it would just error."""
    conn = _fake_conn([("issues", "id")])

    missing = find_missing_pg_columns(conn)

    assert all(table == "issues" for table, _ in missing)


def test_repair_adds_only_the_missing_column():
    conn = _fake_conn([("assembled_issues", "id")])
    raw = conn.raw
    raw.autocommit = False

    with patch("weeklyamp.db.postgres.get_pg_connection", return_value=conn):
        repaired = run_pg_column_repairs("postgresql://fake")

    assert ("assembled_issues", "preheader_text") in repaired
    executed = [c.args[0] for c in raw.cursor.return_value.execute.call_args_list]
    assert any("preheader_text" in sql for sql in executed)
    # Only assembled_issues exists, so nothing else should have been touched.
    assert all("assembled_issues" in sql for sql in executed)


def test_one_failing_statement_does_not_abort_the_rest():
    """In PostgreSQL a failed statement poisons its transaction, so each
    repair must run independently."""
    conn = _fake_conn([("assembled_issues", "id"), ("issues", "id")])
    raw = conn.raw
    raw.autocommit = False

    calls: list[str] = []

    def flaky_execute(sql):
        calls.append(sql)
        if "web_html" in sql:
            raise RuntimeError("boom")

    raw.cursor.return_value.execute.side_effect = flaky_execute

    with patch("weeklyamp.db.postgres.get_pg_connection", return_value=conn):
        repaired = run_pg_column_repairs("postgresql://fake")

    assert any("web_html" in sql for sql in calls), "the failing statement ran"
    assert ("assembled_issues", "web_html") not in repaired, "failure not counted as repaired"
    assert ("assembled_issues", "preheader_text") in repaired, "later repairs still applied"


def test_no_repairs_needed_is_a_no_op():
    every_column = [(t, c) for t, c in PG_COLUMN_REPAIRS]
    conn = _fake_conn(every_column)

    with patch("weeklyamp.db.postgres.get_pg_connection", return_value=conn):
        repaired = run_pg_column_repairs("postgresql://fake")

    assert repaired == []
    conn.raw.cursor.assert_not_called()
