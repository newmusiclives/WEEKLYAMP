"""Tests for the public subscriber-bearer-token routes.

Pre-fix, `/preferences/{token}` and `/refer/dashboard/{token}` queried
a `preference_token` column that does NOT exist in the schema —
preferences raised OperationalError → 500, and refer's wider
try/except masked it as "Invalid link" for every legitimate
subscriber. The fix unifies on `unsubscribe_token` (which exists, is
256-bit random, and already gates `/my-dashboard`).

Asserts:
  1. /preferences/{valid_unsub_token} renders the preferences form
  2. /preferences/{invalid_token} returns 404 with the friendly page
  3. POST /preferences/{token} actually persists the update (lookup
     UPDATE used to fail because it referenced the same missing column)
  4. /refer/dashboard/{valid_unsub_token} renders, not "Invalid link"
  5. /refer/dashboard/{invalid_token} → 404
  6. The token route is rate limited — 31 hits in quick succession
     start hitting 429 (defense in depth even though the token is
     mathematically un-brute-forceable)
"""

from __future__ import annotations

import secrets

import pytest

from weeklyamp.core.feature_flags import FeatureFlag, invalidate_cache


@pytest.fixture(autouse=True)
def _enable_referrals_flag(repo):
    """The /refer/* router is gated behind the REFERRALS feature flag.
    Without it the dashboard 404s before our auth check ever runs."""
    repo.set_feature_flag(FeatureFlag.REFERRALS, True)
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture()
def subscriber_with_token(repo):
    """Create a subscriber with a known unsubscribe_token. Returns
    {id, email, token}."""
    repo.upsert_subscriber(email="bearer@example.com")
    token = secrets.token_urlsafe(32)
    conn = repo._conn()
    conn.execute(
        "UPDATE subscribers SET unsubscribe_token = ? WHERE email = ?",
        (token, "bearer@example.com"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM subscribers WHERE email = ?", ("bearer@example.com",),
    ).fetchone()
    conn.close()
    return {"id": row["id"], "email": "bearer@example.com", "token": token}


# ---- /preferences/{token} ----------------------------------------------


def test_preferences_page_with_valid_token_renders(client, subscriber_with_token):
    r = client.get(f"/preferences/{subscriber_with_token['token']}")
    assert r.status_code == 200
    assert "bearer@example.com" in r.text or "preferences" in r.text.lower()


def test_preferences_page_with_invalid_token_returns_404(client):
    r = client.get("/preferences/not-a-real-token-xxxxxxxxxxxxxxxxxxxxx")
    assert r.status_code == 404
    assert "Invalid or expired link" in r.text


def test_preferences_post_actually_updates_row(client, repo, subscriber_with_token):
    """Pre-fix: the UPDATE used `WHERE preference_token = ?` (a missing
    column) so it silently affected zero rows. This test would have
    failed pre-fix because the row's editions field would not change."""
    sub_id = subscriber_with_token["id"]
    token = subscriber_with_token["token"]

    r = client.post(
        f"/preferences/{token}",
        data={
            "editions": ["fan", "artist"],
            "send_days": ["mon", "wed"],
            "content_frequency": "weekly_digest",
            "timezone": "America/Chicago",
            "interests": "live shows; new releases",
        },
    )
    assert r.status_code == 200

    # Preferences live in subscriber_preferences; editions live in
    # subscriber_editions joined to newsletter_editions on edition_id.
    prefs = repo.get_subscriber_preferences(sub_id)
    assert prefs is not None
    assert prefs["content_frequency"] == "weekly_digest"
    assert prefs["timezone"] == "America/Chicago"
    assert prefs["interests"] == "live shows; new releases"

    conn = repo._conn()
    rows = conn.execute(
        """SELECT ne.slug, se.send_days FROM subscriber_editions se
           JOIN newsletter_editions ne ON ne.id = se.edition_id
           WHERE se.subscriber_id = ?""",
        (sub_id,),
    ).fetchall()
    conn.close()
    by_slug = {r["slug"]: r["send_days"] for r in rows}
    # The form passed editions=["fan", "artist"] — both should be
    # subscribed with the chosen send_days. 'mon' / 'wed' are the
    # short forms the form supplied; we don't expand them so the
    # raw CSV is what's stored.
    assert "fan" in by_slug
    assert "artist" in by_slug
    assert by_slug["fan"] == "mon,wed"


# ---- /refer/dashboard/{token} ------------------------------------------


def test_refer_dashboard_with_valid_token_renders(client, subscriber_with_token):
    r = client.get(f"/refer/dashboard/{subscriber_with_token['token']}")
    assert r.status_code == 200
    # Pre-fix this returned the "Invalid or expired link" 404 even
    # for valid subscribers because the lookup was broken.
    assert "Invalid or expired link" not in r.text


def test_refer_dashboard_with_invalid_token_returns_404(client):
    r = client.get("/refer/dashboard/not-a-real-token-xxxxxxxxxxxxxxxxxxxxx")
    assert r.status_code == 404


# ---- Rate limit -------------------------------------------------------


def test_token_routes_are_rate_limited(client):
    """30 requests/min is the configured limit. 31 hits in quick
    succession from the same IP should start producing 429s. We test
    the invalid-token case so we don't need DB state — the rate limit
    fires before the lookup."""
    bad_token = "rate-test-token-doesnt-exist-yyyyy"
    statuses: list[int] = []
    for _ in range(35):
        r = client.get(f"/preferences/{bad_token}")
        statuses.append(r.status_code)
    # First batch should be 404 (token invalid), then 429 once the
    # per-minute limit is exhausted.
    assert 429 in statuses, (
        f"expected at least one 429 after 35 requests; saw statuses: {statuses[:5]}...{statuses[-5:]}"
    )
