"""Regression test for the Postgres connection-pool leak that took down
production on 2026-04-08.

The Repository layer follows a `conn = self._conn(); ...; conn.close()`
pattern with no try/finally. If a query inside that block raises, the
explicit `close()` is never reached and the pooled connection never
gets returned. With a hot loop (the scheduler runs every 60s) the pool
empties in minutes and the entire service becomes unavailable.

The fix: PgConnection registers a `weakref.finalize` callback in
__init__ that returns the connection to the pool when the wrapper is
GC'd, even if `close()` was never called. `close()` detaches the
finalizer first so the connection is not double-returned on the happy
path.

These tests verify the safety net by:
  1. Asserting that abandoning a PgConnection wrapper without calling
     close() still triggers a `putconn` (the leak fix).
  2. Asserting that calling close() yields exactly one putconn even
     after the wrapper is later GC'd (no double-return).
"""

from __future__ import annotations

import gc
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def fake_pool():
    """Patch the module-level _get_pool to return a MagicMock pool."""
    pool = MagicMock()
    pool.getconn.return_value = MagicMock(name="pg_conn")
    with patch("weeklyamp.db.postgres._get_pool", return_value=pool):
        yield pool


def test_abandoned_connection_is_returned_to_pool_via_finalizer(fake_pool):
    """If the wrapper is dropped without close() — the exact failure
    pattern that caused the production outage — the finalizer must
    return the connection to the pool."""
    from weeklyamp.db.postgres import PgConnection

    conn = PgConnection("postgresql://fake", use_pool=True)
    raw = conn._conn  # capture before we drop the wrapper

    # Drop the only reference and force GC. CPython will reclaim the
    # local immediately on refcount drop, but we trigger gc.collect()
    # explicitly to be deterministic across implementations.
    del conn
    gc.collect()

    fake_pool.putconn.assert_called_once_with(raw)


def test_explicit_close_returns_exactly_once(fake_pool):
    """Happy path: close() returns the connection. The finalizer is
    detached so a later GC pass does NOT double-return it."""
    from weeklyamp.db.postgres import PgConnection

    conn = PgConnection("postgresql://fake", use_pool=True)
    raw = conn._conn

    conn.close()
    assert fake_pool.putconn.call_count == 1
    fake_pool.putconn.assert_called_with(raw)

    # Now drop the wrapper and force GC. The finalizer must be a
    # no-op because close() detached it.
    del conn
    gc.collect()
    assert fake_pool.putconn.call_count == 1, (
        "Connection was returned twice — the finalizer was not detached "
        "by close(), which means under load we'd putconn() the same "
        "underlying connection twice and corrupt the pool."
    )


def test_double_close_is_safe(fake_pool):
    """Calling close() twice should be a no-op on the second call."""
    from weeklyamp.db.postgres import PgConnection

    conn = PgConnection("postgresql://fake", use_pool=True)
    conn.close()
    conn.close()
    assert fake_pool.putconn.call_count == 1
