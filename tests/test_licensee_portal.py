"""Tests for the licensee portal authentication and dashboard.

These guard against the placeholder auth bug where `if password != email`
silently allowed anyone to log in as a licensee using their email as the
password. See licensee_portal.py history for context.
"""

from __future__ import annotations

import pytest

from weeklyamp.web.security import hash_password


@pytest.fixture(autouse=True)
def _enable_white_label(tmp_db):
    """These tests exercise the white-label licensee portal, which is
    now behind the `white_label` feature flag. Pre-seed the flag to on
    BEFORE the app starts (via `client`) so seed_from_config (which
    only writes when no row exists) doesn't overwrite, and drop any
    cached False value from a previous test.
    """
    from weeklyamp.core import feature_flags as ff
    from weeklyamp.db.repository import Repository

    Repository(tmp_db).set_feature_flag("white_label", True)
    ff.invalidate_cache()
    yield
    ff.invalidate_cache()


@pytest.fixture()
def licensee(repo):
    """Create an active licensee with a known bcrypt password."""
    licensee_id = repo.create_licensee(
        company_name="Test Music LLC",
        contact_name="Test Operator",
        email="op@example.com",
        password_hash=hash_password("correct-horse-battery-staple"),
        city_market_slug="test-city",
        edition_slugs="fan",
        license_type="monthly",
        license_fee_cents=9900,
        revenue_share_pct=20.0,
    )
    # Newly created licensees default to status='pending' — promote to active.
    repo.update_licensee_status(licensee_id, "active")
    return repo.get_licensee(licensee_id)


def test_login_page_renders(client):
    resp = client.get("/licensee/login")
    assert resp.status_code == 200


def test_login_with_correct_password_sets_session(client, licensee):
    resp = client.post(
        "/licensee/login",
        data={"email": "op@example.com", "password": "correct-horse-battery-staple"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/licensee/dashboard"
    assert "_licensee_session" in resp.cookies


def test_login_with_wrong_password_returns_401(client, licensee):
    resp = client.post(
        "/licensee/login",
        data={"email": "op@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert "_licensee_session" not in resp.cookies


def test_login_with_password_equal_to_email_is_rejected(client, licensee):
    """Regression: the old placeholder allowed `password == email` to log in.

    This test must always fail to authenticate when the password equals the
    email — proving the placeholder fallback has been removed.
    """
    resp = client.post(
        "/licensee/login",
        data={"email": "op@example.com", "password": "op@example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert "_licensee_session" not in resp.cookies


def test_login_unknown_email_returns_401(client):
    resp = client.post(
        "/licensee/login",
        data={"email": "ghost@example.com", "password": "anything"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert "_licensee_session" not in resp.cookies


def test_login_blocked_when_status_not_active(client, repo, licensee):
    repo.update_licensee_status(licensee["id"], "suspended")
    resp = client.post(
        "/licensee/login",
        data={"email": "op@example.com", "password": "correct-horse-battery-staple"},
        follow_redirects=False,
    )
    assert resp.status_code == 403
    assert "_licensee_session" not in resp.cookies


def test_dashboard_without_session_redirects_to_login(client):
    resp = client.get("/licensee/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/licensee/login"


def test_dashboard_with_valid_session_returns_200(client, licensee):
    # Authenticate
    login = client.post(
        "/licensee/login",
        data={"email": "op@example.com", "password": "correct-horse-battery-staple"},
        follow_redirects=False,
    )
    assert login.status_code == 302
    # Cookie is now set on the TestClient — request the dashboard
    resp = client.get("/licensee/dashboard")
    assert resp.status_code == 200


def test_dashboard_query_param_does_not_grant_access(client, licensee):
    """Regression: the old route accepted `?licensee_id=N` as auth.

    Even with a real licensee id in the query string, an unauthenticated
    request must not be able to view another licensee's dashboard.
    """
    resp = client.get(
        f"/licensee/dashboard?licensee_id={licensee['id']}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/licensee/login"


def test_logout_clears_session(client, licensee):
    client.post(
        "/licensee/login",
        data={"email": "op@example.com", "password": "correct-horse-battery-staple"},
        follow_redirects=False,
    )
    assert client.get("/licensee/dashboard").status_code == 200
    client.get("/licensee/logout", follow_redirects=False)
    # After logout the dashboard must redirect to login
    resp = client.get("/licensee/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/licensee/login"
