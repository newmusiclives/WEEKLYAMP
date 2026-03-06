"""Shared fixtures for WEEKLYAMP test suite."""

from __future__ import annotations

import os
import pytest


@pytest.fixture()
def tmp_db(tmp_path):
    """Create a temporary SQLite database with schema, sections, and editions seeded."""
    db_file = str(tmp_path / "test.db")
    from weeklyamp.core.database import init_database, seed_sections, seed_editions
    init_database(db_file)
    seed_sections(db_file)
    seed_editions(db_file)
    return db_file


@pytest.fixture()
def repo(tmp_db):
    """Return a Repository connected to the temporary database."""
    from weeklyamp.db.repository import Repository
    return Repository(tmp_db)


@pytest.fixture()
def client(tmp_db, monkeypatch):
    """Return a Starlette TestClient wired to the app with a temp DB.

    Environment variables are patched so that the app factory and all
    route helpers resolve the temporary database.
    """
    monkeypatch.setenv("WEEKLYAMP_DB_PATH", tmp_db)
    # Disable admin auth so public/health routes work without password setup
    monkeypatch.delenv("WEEKLYAMP_ADMIN_HASH", raising=False)
    monkeypatch.delenv("WEEKLYAMP_ADMIN_PASSWORD", raising=False)

    # Reset the cached admin hash so the monkeypatched env takes effect
    import weeklyamp.web.security as _sec
    _sec._cached_admin_hash = None

    from weeklyamp.web.app import create_app
    from starlette.testclient import TestClient

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc

    # Reset cached hash for subsequent tests
    _sec._cached_admin_hash = None
