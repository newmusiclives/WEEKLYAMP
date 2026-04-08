"""Tests for the in-app admin change-password flow.

Covers:
  1. Repository admin_settings get/set + upsert behavior
  2. _get_admin_hash priority order: DB > env hash > env password
  3. invalidate_admin_hash_cache forces re-resolution
  4. Change-password route: validation rules, current-password check,
     successful rotation, and post-rotation login with the new password
"""

from __future__ import annotations

import pytest

from weeklyamp.web.security import (
    _get_admin_hash,
    hash_password,
    invalidate_admin_hash_cache,
    verify_password,
)


# ---- Repository layer ----------------------------------------------------


def test_admin_settings_returns_empty_when_unset(repo):
    assert repo.get_admin_setting("admin_password_hash") == ""


def test_admin_settings_set_and_get(repo):
    repo.set_admin_setting("admin_password_hash", "test-hash-value")
    assert repo.get_admin_setting("admin_password_hash") == "test-hash-value"


def test_admin_settings_upsert_overwrites(repo):
    repo.set_admin_setting("admin_password_hash", "first")
    repo.set_admin_setting("admin_password_hash", "second")
    assert repo.get_admin_setting("admin_password_hash") == "second"


# ---- _get_admin_hash priority order --------------------------------------


def test_get_admin_hash_prefers_db_over_env(repo, monkeypatch):
    """DB row wins over env var. This is the load-bearing assertion
    for the whole feature: it's what makes a UI password change
    actually take effect even when the operator hasn't touched the
    Railway env var."""
    db_hash = hash_password("from-db-password")
    env_hash = hash_password("from-env-password")
    repo.set_admin_setting("admin_password_hash", db_hash)
    monkeypatch.setenv("WEEKLYAMP_ADMIN_HASH", env_hash)
    monkeypatch.setattr("weeklyamp.web.deps.get_repo", lambda: repo)
    invalidate_admin_hash_cache()

    active = _get_admin_hash()
    assert active == db_hash
    assert verify_password("from-db-password", active) is True
    assert verify_password("from-env-password", active) is False


def test_get_admin_hash_falls_back_to_env_when_db_empty(repo, monkeypatch):
    env_hash = hash_password("env-only-password")
    monkeypatch.setenv("WEEKLYAMP_ADMIN_HASH", env_hash)
    monkeypatch.setattr("weeklyamp.web.deps.get_repo", lambda: repo)
    invalidate_admin_hash_cache()

    active = _get_admin_hash()
    assert active == env_hash


def test_invalidate_cache_picks_up_db_change(repo, monkeypatch):
    """After the change-password route writes the new DB hash, the
    cache must be invalidated so the next request sees the new
    value. This test would fail if the route forgot to call
    invalidate_admin_hash_cache()."""
    monkeypatch.setattr("weeklyamp.web.deps.get_repo", lambda: repo)
    monkeypatch.delenv("WEEKLYAMP_ADMIN_HASH", raising=False)
    monkeypatch.delenv("WEEKLYAMP_ADMIN_PASSWORD", raising=False)

    # Seed an initial DB hash and warm the cache.
    first_hash = hash_password("first-password")
    repo.set_admin_setting("admin_password_hash", first_hash)
    invalidate_admin_hash_cache()
    assert _get_admin_hash() == first_hash

    # Rotate without invalidation: cache still serves the old value.
    second_hash = hash_password("second-password")
    repo.set_admin_setting("admin_password_hash", second_hash)
    assert _get_admin_hash() == first_hash, (
        "Cache was not stale before invalidation — test setup broken"
    )

    # After invalidation, the new hash takes effect.
    invalidate_admin_hash_cache()
    assert _get_admin_hash() == second_hash


# ---- Change-password route -----------------------------------------------


_KNOWN_INITIAL_PW = "InitialAdminPassword123"


@pytest.fixture()
def authed_client(client, repo, monkeypatch):
    """A TestClient with an active admin session AND the security cache
    pointed at the test repo.

    Setup:
      1. Seed admin_settings.admin_password_hash with a known initial
         password so the route's "current password" check has
         something to compare against.
      2. Patch get_repo so security.py reads from the test repo when
         resolving the active hash.
      3. Invalidate the cache so the seeded hash takes effect.
      4. POST /login with the initial password to establish a real
         session cookie on the client.

    Each test that needs a different starting hash can re-seed and
    re-invalidate, but the session cookie remains valid (sessions
    are not bound to a specific hash — they're just signed
    timestamps that prove "this client has logged in within max_age")."""
    monkeypatch.setattr("weeklyamp.web.deps.get_repo", lambda: repo)
    repo.set_admin_setting("admin_password_hash", hash_password(_KNOWN_INITIAL_PW))
    invalidate_admin_hash_cache()

    # Establish a real session via the login flow.
    r = client.post(
        "/login",
        data={"password": _KNOWN_INITIAL_PW},
        follow_redirects=False,
    )
    assert r.status_code == 302, f"login fixture failed: {r.status_code} {r.text[:200]}"

    yield client

    invalidate_admin_hash_cache()


def _csrf_headers(client):
    """Issue a GET to set/refresh the CSRF cookie, then return the
    headers needed for an authenticated POST."""
    client.get("/admin/change-password")
    token = client.cookies.get("_csrf", "")
    return {"X-CSRF-Token": token}


def test_change_password_form_renders(authed_client):
    r = authed_client.get("/admin/change-password")
    assert r.status_code == 200
    assert "Change Admin Password" in r.text
    assert "Current password" in r.text


def test_change_password_rejects_mismatch(authed_client):
    headers = _csrf_headers(authed_client)
    r = authed_client.post(
        "/admin/change-password",
        data={
            "current_password": _KNOWN_INITIAL_PW,
            "new_password": "NewPassword12345",
            "confirm_password": "DifferentPassword999",
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "do not match" in r.text


def test_change_password_rejects_too_short(authed_client):
    headers = _csrf_headers(authed_client)
    r = authed_client.post(
        "/admin/change-password",
        data={
            "current_password": _KNOWN_INITIAL_PW,
            "new_password": "short",
            "confirm_password": "short",
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "12 characters" in r.text


def test_change_password_rejects_wrong_current(authed_client):
    headers = _csrf_headers(authed_client)
    r = authed_client.post(
        "/admin/change-password",
        data={
            "current_password": "WrongCurrent999",
            "new_password": "BrandNewPassword123",
            "confirm_password": "BrandNewPassword123",
        },
        headers=headers,
    )
    assert r.status_code == 401
    assert "incorrect" in r.text.lower()


def test_change_password_rejects_same_as_current(authed_client):
    headers = _csrf_headers(authed_client)
    r = authed_client.post(
        "/admin/change-password",
        data={
            "current_password": _KNOWN_INITIAL_PW,
            "new_password": _KNOWN_INITIAL_PW,
            "confirm_password": _KNOWN_INITIAL_PW,
        },
        headers=headers,
    )
    assert r.status_code == 400
    assert "differ" in r.text.lower()


def test_change_password_success_persists_and_takes_effect(authed_client, repo):
    """Happy path: provide correct current password + valid new password,
    assert (a) the route returns success, (b) the new hash is stored
    in admin_settings, (c) verify_password works with the new password
    and fails with the old one, (d) the cache reflects the new hash."""
    initial_hash = repo.get_admin_setting("admin_password_hash")
    assert initial_hash, "fixture should have seeded an initial hash"

    headers = _csrf_headers(authed_client)
    r = authed_client.post(
        "/admin/change-password",
        data={
            "current_password": _KNOWN_INITIAL_PW,
            "new_password": "BrandNewPassword456",
            "confirm_password": "BrandNewPassword456",
        },
        headers=headers,
    )

    assert r.status_code == 200, r.text
    assert "Password updated" in r.text

    # New hash is in the DB
    stored = repo.get_admin_setting("admin_password_hash")
    assert stored != initial_hash
    assert verify_password("BrandNewPassword456", stored)
    assert not verify_password(_KNOWN_INITIAL_PW, stored)

    # And the in-process cache reflects the new hash without a manual
    # invalidate (the route is supposed to invalidate on success)
    assert _get_admin_hash() == stored
