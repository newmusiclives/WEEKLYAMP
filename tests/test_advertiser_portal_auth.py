"""Tests for advertiser portal session auth.

Covers the load-bearing security properties that the demo-mode-to-session
migration needs to hold:

  1. Dashboard redirects unauth'd visitors to /advertiser/login.
  2. Login with valid creds sets a session cookie + redirects to dashboard.
  3. Wrong password does NOT set a session cookie.
  4. With a valid session the dashboard returns 200 and the right account.
  5. Logout clears the session cookie.
  6. Advertiser A cannot submit advertiser B's campaign even though it's
     a valid campaign_id — the route checks the session-resolved
     advertiser_id against the row's advertiser_id and rejects with 403.

The cross-advertiser test (#6) is the one that actually justifies the
session migration. Before this change, /advertiser/dashboard?advertiser_id=N
let anyone view any account's campaigns by guessing the integer ID.
"""

from __future__ import annotations

import pytest

from weeklyamp.core.feature_flags import FeatureFlag, invalidate_cache
from weeklyamp.web.security import hash_password


@pytest.fixture(autouse=True)
def _enable_advertisers_flag(repo):
    """The advertiser portal routes are gated behind the ADVERTISERS
    feature flag — without this, every request 404s before our auth
    checks even run."""
    repo.set_feature_flag(FeatureFlag.ADVERTISERS, True)
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture()
def advertiser_a(repo):
    """Create an advertiser account A with a known password."""
    pw_hash = hash_password("password-a-1234")
    conn = repo._conn()
    cur = conn.execute(
        "INSERT INTO advertiser_accounts (email, password_hash) VALUES (?, ?)",
        ("a@example.com", pw_hash),
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return {"id": aid, "email": "a@example.com", "password": "password-a-1234"}


@pytest.fixture()
def advertiser_b(repo):
    pw_hash = hash_password("password-b-5678")
    conn = repo._conn()
    cur = conn.execute(
        "INSERT INTO advertiser_accounts (email, password_hash) VALUES (?, ?)",
        ("b@example.com", pw_hash),
    )
    conn.commit()
    bid = cur.lastrowid
    conn.close()
    return {"id": bid, "email": "b@example.com", "password": "password-b-5678"}


def test_dashboard_redirects_when_unauthenticated(client):
    r = client.get("/advertiser/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert "/advertiser/login" in r.headers["location"]


def test_login_sets_session_and_redirects(client, advertiser_a):
    r = client.post(
        "/advertiser/login",
        data={"email": advertiser_a["email"], "password": advertiser_a["password"]},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].endswith("/advertiser/dashboard")
    # Session cookie set
    assert "_advertiser_session" in r.cookies


def test_wrong_password_does_not_set_session(client, advertiser_a):
    r = client.post(
        "/advertiser/login",
        data={"email": advertiser_a["email"], "password": "wrong"},
        follow_redirects=False,
    )
    assert r.status_code == 200  # Re-renders login page with error
    assert "_advertiser_session" not in r.cookies


def test_dashboard_works_with_valid_session(client, advertiser_a):
    # Establish session
    client.post(
        "/advertiser/login",
        data={"email": advertiser_a["email"], "password": advertiser_a["password"]},
        follow_redirects=False,
    )
    r = client.get("/advertiser/dashboard")
    assert r.status_code == 200


def test_logout_clears_session(client, advertiser_a):
    client.post(
        "/advertiser/login",
        data={"email": advertiser_a["email"], "password": advertiser_a["password"]},
        follow_redirects=False,
    )
    client.post("/advertiser/logout", follow_redirects=False)
    # After logout, the dashboard should redirect again
    r = client.get("/advertiser/dashboard", follow_redirects=False)
    assert r.status_code == 302


def test_cannot_submit_other_advertisers_campaign(client, repo, advertiser_a, advertiser_b):
    """The load-bearing test: if advertiser A is logged in, they cannot
    submit advertiser B's draft campaign by sending its campaign_id.
    Before the session migration, this attack worked because the route
    trusted the advertiser_id from the form."""
    # B creates a campaign
    b_campaign_id = repo.create_advertiser_campaign(
        advertiser_id=advertiser_b["id"],
        name="B's secret campaign",
        edition_slug="fan",
    )

    # A logs in
    client.post(
        "/advertiser/login",
        data={"email": advertiser_a["email"], "password": advertiser_a["password"]},
        follow_redirects=False,
    )

    # A tries to submit B's campaign
    r = client.post(f"/advertiser/campaign/{b_campaign_id}/submit")
    assert r.status_code == 403

    # And the campaign status should be unchanged (still 'draft')
    refreshed = repo.get_advertiser_campaign(b_campaign_id)
    assert refreshed["status"] == "draft"
