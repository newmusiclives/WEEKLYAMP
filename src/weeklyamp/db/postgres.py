"""PostgreSQL connection manager mirroring the SQLite interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

_SCHEMA_PG_PATH = Path(__file__).parent / "schema_pg.sql"


class PgConnection:
    """Thin wrapper around a psycopg2 connection that provides a dict-row
    interface compatible with the SQLite ``sqlite3.Row`` usage in the
    Repository layer.

    Key differences from raw psycopg2:
    - ``execute()`` returns a cursor (matching sqlite3 API).
    - ``fetchone()`` / ``fetchall()`` return dicts.
    - Provides ``lastrowid`` on the cursor returned by ``execute()``
      via ``RETURNING id`` support (caller must append it to INSERTs).
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = False

    # -- Context-manager support (matches sqlite3.Connection) --

    def __enter__(self) -> "PgConnection":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- Core interface --

    def execute(self, sql: str, params: Any = None) -> "PgCursor":
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return PgCursor(cur)

    def executescript(self, sql: str) -> None:
        """Run a multi-statement SQL script (used for schema init / migrations)."""
        old_autocommit = self._conn.autocommit
        self._conn.autocommit = True
        cur = self._conn.cursor()
        cur.execute(sql)
        cur.close()
        self._conn.autocommit = old_autocommit

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    @property
    def raw(self):
        """Access the underlying psycopg2 connection (escape hatch)."""
        return self._conn


class PgCursor:
    """Wraps a psycopg2 RealDictCursor to expose ``fetchone`` / ``fetchall``
    returning plain dicts.

    The ``lastrowid`` attribute is not auto-populated here; the
    ``_PgConnAdapter`` in repository.py handles ``RETURNING id`` logic
    when used through the Repository layer.
    """

    def __init__(self, cur: psycopg2.extras.RealDictCursor) -> None:
        self._cur = cur
        self.lastrowid: Optional[int] = None

    def fetchone(self) -> Optional[dict]:
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict]:
        rows = self._cur.fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._cur.close()


def get_pg_connection(database_url: str) -> PgConnection:
    """Return a PostgreSQL connection wrapper."""
    return PgConnection(database_url)


def init_pg_database(database_url: str) -> None:
    """Run the PostgreSQL schema SQL to create all tables, then apply pending migrations."""
    conn = get_pg_connection(database_url)
    schema_sql = _SCHEMA_PG_PATH.read_text()
    conn.executescript(schema_sql)
    conn.close()

    # Run migrations for existing databases that need schema updates
    from weeklyamp.db.migrations import run_pg_migrations
    run_pg_migrations(database_url)


def get_pg_schema_version(database_url: str) -> Optional[int]:
    """Return the current schema version, or None if table doesn't exist."""
    conn = get_pg_connection(database_url)
    try:
        cur = conn.execute("SELECT MAX(version) as v FROM schema_version")
        row = cur.fetchone()
        return row["v"] if row else None
    except psycopg2.Error:
        conn.rollback()
        return None
    finally:
        conn.close()
