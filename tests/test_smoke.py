"""Live smoke tests against a running deployment.

These tests are *not* run in the default pytest suite — they require a
live URL and a valid admin password, so they're marked ``live`` and
must be invoked explicitly:

    SMOKE_URL=https://... SMOKE_ADMIN_PASSWORD=... pytest -m live tests/test_smoke.py

Smoke coverage:
  - /health returns 200 (app alive + DB reachable)
  - /login GET returns 200 (login template renders)
  - /login POST with correct password returns 302 → /dashboard (auth works end-to-end)
  - /login POST with wrong password returns 401 (negative path works)
  - /admin/feature-flags returns 200 when authenticated (feature flag UI lives)

Golden path for a green launch: every case above passes.
"""

from __future__ import annotations

import os

import httpx
import pytest


SMOKE_URL = os.environ.get("SMOKE_URL", "").rstrip("/")
SMOKE_ADMIN_PASSWORD = os.environ.get("SMOKE_ADMIN_PASSWORD", "")


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not SMOKE_URL, reason="SMOKE_URL not set"),
]


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=SMOKE_URL, follow_redirects=False, timeout=15.0) as c:
        yield c


@pytest.fixture(scope="module")
def authed_client():
    if not SMOKE_ADMIN_PASSWORD:
        pytest.skip("SMOKE_ADMIN_PASSWORD not set")
    with httpx.Client(base_url=SMOKE_URL, follow_redirects=False, timeout=15.0) as c:
        r = c.post("/login", data={"password": SMOKE_ADMIN_PASSWORD})
        assert r.status_code == 302, f"login failed: {r.status_code} {r.text[:200]}"
        assert r.headers.get("location") == "/dashboard"
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "TrueFans SIGNAL" in r.text
    assert "password" in r.text.lower()


def test_login_wrong_password_rejected(client):
    r = client.post("/login", data={"password": "definitely-not-the-password"})
    assert r.status_code in (401, 429)  # 429 if hard-locked from previous runs


def test_login_correct_password_succeeds(authed_client):
    # Fixture already verified the happy path; this test just asserts
    # the fixture session is usable for a follow-up authed request.
    r = authed_client.get("/dashboard")
    assert r.status_code == 200


def test_feature_flags_admin_page(authed_client):
    r = authed_client.get("/admin/feature-flags")
    assert r.status_code == 200
    assert "Feature Flags" in r.text
