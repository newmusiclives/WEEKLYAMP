"""PostgreSQL connection manager with connection pooling."""

from __future__ import annotations

import logging
import os
import weakref
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

_SCHEMA_PG_PATH = Path(__file__).parent / "schema_pg.sql"

# Connection pool singleton
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def _get_pool(dsn: str) -> psycopg2.pool.ThreadedConnectionPool:
    """Get or create the connection pool singleton."""
    global _pool
    if _pool is None or _pool.closed:
        min_conns = int(os.environ.get("PG_POOL_MIN", 2))
        max_conns = int(os.environ.get("PG_POOL_MAX", 10))
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_conns,
            maxconn=max_conns,
            dsn=dsn,
        )
        logger.info("PostgreSQL connection pool created (min=%d, max=%d)", min_conns, max_conns)
    return _pool


def close_pool() -> None:
    """Close the connection pool. Call during application shutdown."""
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        logger.info("PostgreSQL connection pool closed")
        _pool = None


def _safe_putconn(dsn: str, conn) -> None:
    """Return a connection to the pool, swallowing any error.

    Used as a `weakref.finalize` callback on PgConnection so that a
    connection always finds its way back to the pool — even when the
    caller raised an exception before reaching its explicit close().
    Errors here are intentionally swallowed: the finalizer runs at GC
    time, often during interpreter shutdown, when the pool may already
    be closed and there is nothing useful we can do with the failure.
    """
    try:
        pool = _get_pool(dsn)
        pool.putconn(conn)
    except Exception:
        pass


class PgConnection:
    """Thin wrapper around a psycopg2 connection that provides a dict-row
    interface compatible with the SQLite ``sqlite3.Row`` usage in the
    Repository layer.

    When ``use_pool=True`` (default), connections are drawn from a shared pool
    and returned on ``close()``.
    """

    def __init__(self, dsn: str, use_pool: bool = True) -> None:
        self._dsn = dsn
        self._use_pool = use_pool
        self._closed = False
        if use_pool:
            pool = _get_pool(dsn)
            self._conn = pool.getconn()
            # Safety net: return the connection to the pool when this
            # wrapper is garbage-collected, even if the caller forgot
            # to call close(). This is what prevents an unhandled
            # exception inside a Repository method (which has no
            # try/finally around its `conn = self._conn(); ...;
            # conn.close()` block) from leaking a connection on every
            # failure. Without this, one buggy query in a hot loop
            # exhausts the pool in minutes — see incident 2026-04-08.
            self._finalizer = weakref.finalize(
                self, _safe_putconn, dsn, self._conn
            )
        else:
            self._conn = psycopg2.connect(dsn)
            self._finalizer = None
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
        """Run a multi-statement SQL script (used for schema init / migrations).

        psycopg2 refuses to change autocommit mode while a transaction is open,
        so we commit any pending work first before switching into autocommit
        mode to execute the script.
        """
        old_autocommit = self._conn.autocommit
        if not old_autocommit:
            # Close any in-flight transaction from prior queries on this
            # connection; otherwise set_session raises ProgrammingError.
            self._conn.commit()
        self._conn.autocommit = True
        try:
            cur = self._conn.cursor()
            cur.execute(sql)
            cur.close()
        finally:
            self._conn.autocommit = old_autocommit

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._use_pool:
            # Detach the finalizer first so it doesn't double-return the
            # connection when this wrapper is GC'd later.
            if self._finalizer is not None:
                self._finalizer.detach()
            pool = _get_pool(self._dsn)
            try:
                pool.putconn(self._conn)
            except Exception:
                pass
        else:
            self._conn.close()

    @property
    def raw(self):
        """Access the underlying psycopg2 connection (escape hatch)."""
        return self._conn


class PgCursor:
    """Wraps a psycopg2 RealDictCursor to expose ``fetchone`` / ``fetchall``
    returning plain dicts.
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


def get_pg_connection(database_url: str, use_pool: bool = True) -> PgConnection:
    """Return a PostgreSQL connection wrapper."""
    return PgConnection(database_url, use_pool=use_pool)


def init_pg_database(database_url: str) -> None:
    """Run the PostgreSQL schema SQL to create all tables, then apply pending migrations."""
    # Use a non-pooled connection for schema init
    conn = get_pg_connection(database_url, use_pool=False)
    schema_sql = _SCHEMA_PG_PATH.read_text()
    conn.executescript(schema_sql)
    conn.close()

    # Run migrations for existing databases that need schema updates
    from weeklyamp.db.migrations import run_pg_migrations
    run_pg_migrations(database_url)


def get_pg_schema_version(database_url: str) -> Optional[int]:
    """Return the current schema version, or None if table doesn't exist."""
    conn = get_pg_connection(database_url, use_pool=False)
    try:
        cur = conn.execute("SELECT MAX(version) as v FROM schema_version")
        row = cur.fetchone()
        return row["v"] if row else None
    except psycopg2.Error:
        conn.rollback()
        return None
    finally:
        conn.close()
