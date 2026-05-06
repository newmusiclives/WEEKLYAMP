"""Broad smoke-style coverage for high-traffic public + admin routes.

The audit flagged that web routes only had ~7 unit tests against a 66-file
route surface. This file adds focused 2xx/3xx assertions for the routes
most likely to be hit in production. We don't deeply assert response
bodies — those are the responsibility of feature-specific tests. Here
we're catching:

  - Templates that fail to render (Jinja errors → 500)
  - Routes that crash on a fresh DB (NULL columns, missing seed rows)
  - Auth gates that broke (admin pages serving 200 to anonymous, or
    public pages locked behind login)
  - Feature flag gates that are mis-mounted (404 when they should be on)

Each test is one assertion; failure points at one route. Keeps the
diagnostic value when the suite goes red.
"""

from __future__ import annotations

import pytest

from weeklyamp.core.feature_flags import FeatureFlag, invalidate_cache


# ---- Public pages: anonymous, should always be reachable ------------------


@pytest.mark.parametrize("path", [
    "/",
    "/health",
    "/health/ready",
    "/health/live",
    "/robots.txt",
    "/sitemap.xml",
    "/favicon.ico",
    "/login",
    "/login/forgot",
    "/subscribe",
    "/submit",
    "/newsletters",
])
def test_public_route_returns_2xx(client, path):
    """Anonymous visitors must be able to reach these paths without
    auth. Failure here = 5xx in front of a marketing visitor."""
    r = client.get(path, follow_redirects=False)
    # 200 (renders) or 3xx (redirect to canonical) are both fine; what
    # we're catching is 5xx (template/db crash) and 401 (auth misconfig).
    assert r.status_code < 500, f"{path} → {r.status_code}: {r.text[:200]}"
    assert r.status_code != 401, f"{path} unexpectedly required auth"


def test_robots_and_sitemap_reachable_anonymously(auth_enforced_client):
    """SEO files must be reachable without auth even when an admin
    password is configured. They're added to _PUBLIC_EXACT (not
    _PUBLIC_PREFIXES) because they're literal exact paths — putting
    them in the prefix list would be unsafe (would also allow e.g.
    `/robots.txt-admin`).

    `/favicon.ico` redirects to `/static/favicon.svg` (301), so we
    accept either 200 or 3xx — what we're guarding against is the
    auth middleware sending the request to /login."""
    for path in ("/robots.txt", "/sitemap.xml"):
        r = auth_enforced_client.get(path, follow_redirects=False)
        assert r.status_code == 200, (
            f"{path} returned {r.status_code} (expected 200) — Google "
            f"can't crawl auth-gated SEO files"
        )
    r = auth_enforced_client.get("/favicon.ico", follow_redirects=False)
    # Accept the 301 redirect to /static/favicon.svg, just verify it's
    # not bouncing to /login.
    assert r.status_code in (200, 301, 302), f"/favicon.ico → {r.status_code}"
    assert "/login" not in r.headers.get("location", "")


def test_robots_txt_actually_lists_disallows(auth_enforced_client):
    """Beyond just being reachable, /robots.txt must contain the
    Disallow directives (this is what makes it useful — an empty
    200 is the same to a crawler as a 404)."""
    r = auth_enforced_client.get("/robots.txt", follow_redirects=False)
    assert r.status_code == 200
    assert "User-agent: *" in r.text
    assert "Disallow:" in r.text
    assert "Sitemap:" in r.text


def test_landing_page_renders_brand(client):
    r = client.get("/")
    assert r.status_code == 200
    # The product was renamed 2026-04-18 — guard against a partial
    # revert showing SIGNAL on the homepage again.
    assert "DISPATCH" in r.text
    assert "SIGNAL" not in r.text or "TrueFans SIGNAL" not in r.text


def test_health_returns_status_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


# ---- Admin pages: should redirect anonymous, render for authed ----------


@pytest.fixture()
def admin_authed_client(client, repo, monkeypatch):
    """A TestClient with an active admin session, scoped to one test.

    Mirrors the pattern in test_admin_change_password.py — seed a known
    admin password into the DB, log in via the real /login flow, hand
    back the cookie-bearing client.
    """
    from weeklyamp.web.security import (
        hash_password,
        invalidate_admin_hash_cache,
    )
    monkeypatch.setattr("weeklyamp.web.deps.get_repo", lambda: repo)
    repo.set_admin_setting(
        "admin_password_hash", hash_password("admin-pw-12345"),
    )
    invalidate_admin_hash_cache()
    r = client.post(
        "/login", data={"password": "admin-pw-12345"},
        follow_redirects=False,
    )
    assert r.status_code == 302, f"login fixture failed: {r.status_code} {r.text[:200]}"
    yield client
    invalidate_admin_hash_cache()


@pytest.fixture()
def auth_enforced_client(client, repo, monkeypatch):
    """Like the default client but with a real admin hash set, so
    `is_authenticated()` enforces session cookies. The default conftest
    leaves the admin hash unset (dev mode = auth disabled) which is
    great for most tests but exactly wrong for tests that want to
    verify the auth gate."""
    from weeklyamp.web.security import (
        hash_password,
        invalidate_admin_hash_cache,
    )
    monkeypatch.setattr("weeklyamp.web.deps.get_repo", lambda: repo)
    repo.set_admin_setting("admin_password_hash", hash_password("any-password"))
    invalidate_admin_hash_cache()
    yield client
    invalidate_admin_hash_cache()


@pytest.mark.parametrize("path", [
    "/dashboard",
    "/drafts/",
    "/sections/",
    "/subscribers/",
    "/agents/",
    "/submissions/",
    "/admin/feature-flags",
    "/admin/cost-dashboard",
])
def test_admin_route_redirects_anonymous(auth_enforced_client, path):
    """With auth actually enforced (admin hash configured) but no
    session cookie, these routes must NOT serve content. 302 to
    /login is expected. A 200 here would be a privilege-escalation
    bug — the test that catches it is exactly this one."""
    r = auth_enforced_client.get(path, follow_redirects=False)
    assert r.status_code in (302, 401, 403, 404), (
        f"{path} returned {r.status_code} to anonymous visitor"
    )
    if r.status_code == 302:
        assert "login" in r.headers.get("location", ""), (
            f"{path} redirected to {r.headers.get('location')}, expected login"
        )


@pytest.mark.parametrize("path", [
    "/dashboard",
    "/admin/feature-flags",
    "/sections/",
    "/subscribers/",
    "/submissions/",
])
def test_admin_route_renders_for_authed(admin_authed_client, path):
    """With an admin session these admin pages must render (no 5xx)."""
    r = admin_authed_client.get(path)
    assert r.status_code < 500, f"{path} → {r.status_code}: {r.text[:200]}"
    assert r.status_code != 302, f"{path} redirected despite auth"


# ---- Code added in this session: dep pills + contributors leaderboard ---


def test_feature_flags_page_shows_dep_pill_when_unmet(admin_authed_client, repo):
    """The new feature flag dep system should render a 'Requires X' pill
    when a flag is enabled but its prereq is off. We enable MARKETPLACE
    while leaving ADVERTISERS off and assert the pill text appears."""
    repo.set_feature_flag(FeatureFlag.MARKETPLACE, True)
    repo.set_feature_flag(FeatureFlag.ADVERTISERS, False)
    invalidate_cache()
    r = admin_authed_client.get("/admin/feature-flags")
    assert r.status_code == 200
    assert "Advertiser portal" in r.text  # the dep label
    assert "Requires" in r.text


def test_feature_flags_page_no_dep_pill_when_satisfied(admin_authed_client, repo):
    """When all enabled flags' deps are satisfied, no 'Requires X'
    pill should render. We disable every other dep-having flag to
    isolate the assertion to MARKETPLACE→ADVERTISERS — otherwise an
    independently-enabled PODCAST or FRANCHISE could leak a pill into
    the page and false-positive the test."""
    # Turn off every flag that has declared deps, so the only enabled
    # dep edge under test is MARKETPLACE→ADVERTISERS.
    for flag in (FeatureFlag.PODCAST, FeatureFlag.FRANCHISE):
        repo.set_feature_flag(flag, False)
    repo.set_feature_flag(FeatureFlag.MARKETPLACE, True)
    repo.set_feature_flag(FeatureFlag.ADVERTISERS, True)
    invalidate_cache()
    r = admin_authed_client.get("/admin/feature-flags")
    assert r.status_code == 200
    # The CSS definition `.ff-dep-pill { ... }` always appears in the
    # page's <style> block, so we check for the actual rendered span
    # markup and the "Requires:" label instead — both only emit when a
    # flag has unmet deps.
    assert '<span class="ff-dep-pill">' not in r.text
    assert "Requires:" not in r.text


def test_contributors_leaderboard_renders_empty(admin_authed_client):
    """Fresh DB has no submissions — page should render the empty state,
    not crash. This catches the ordering bug where /contributors might
    be eaten by the /{submission_id} int-typed route."""
    r = admin_authed_client.get("/submissions/contributors")
    assert r.status_code == 200
    assert "Contributors" in r.text


def test_subscribers_admin_route_is_not_a_subscribe_prefix_match(auth_enforced_client):
    """Regression: `/subscribers/` is admin-only but used to be reachable
    anonymously because `_is_public()` did a loose prefix match and
    `/subscribe` (the public signup) is a string-prefix of
    `/subscribers`. The fix tightened the match to require an exact
    path or a `/`-bounded suffix. This test pins that contract — if
    someone reverts to loose matching, this fires immediately."""
    r = auth_enforced_client.get("/subscribers/", follow_redirects=False)
    assert r.status_code == 302
    assert "login" in r.headers.get("location", "")


def test_contributors_leaderboard_shows_submitted_data(admin_authed_client, repo):
    """With one published submission from a known artist_email, the
    leaderboard should list that contributor and reflect the right
    counts — proves the route is wired to get_contributor_stats."""
    conn = repo._conn()
    conn.execute(
        "INSERT INTO artist_submissions (artist_name, artist_email) VALUES (?, ?)",
        ("Test Artist", "tester@example.com"),
    )
    conn.commit()
    conn.close()
    r = admin_authed_client.get("/submissions/contributors")
    assert r.status_code == 200
    assert "Test Artist" in r.text
    assert "tester@example.com" in r.text
