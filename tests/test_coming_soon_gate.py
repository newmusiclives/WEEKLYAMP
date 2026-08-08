"""Tests for the pre-launch coming-soon gate.

The gate hides the site before launch, but a few paths must stay reachable
or things break in ways that are hard to spot: uptime monitors need /health,
the holding page itself posts to /coming-soon, email pixels and click
redirects live under /t, and /license is the CTA target for the sponsor
blocks in the sample newsletters — samples get forwarded to prospective
licensees who have no preview cookie, so gating it turns every ad in every
sample into a dead end.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from weeklyamp.web.security import ComingSoonMiddleware

TOKEN = "test-preview-token"


@pytest.fixture(autouse=True)
def anonymous_visitor(monkeypatch):
    """Model a real visitor: not logged in, with auth actually configured.

    `is_authenticated()` returns True for everyone when no admin password is
    set (the dev-mode escape hatch at security.py:487). Without this the gate
    silently never engages and every test here passes vacuously.
    """
    monkeypatch.setattr("weeklyamp.web.security.is_authenticated", lambda request: False)


def _client(enabled: bool = True, token: str = TOKEN) -> TestClient:
    app = FastAPI()
    app.add_middleware(ComingSoonMiddleware, enabled=enabled, token=token)

    @app.get("/{path:path}")
    def catch_all(path: str):
        return PlainTextResponse(f"real page: /{path}")

    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/samples", "/for-artists", "/edition/1"])
def test_public_pages_are_gated(path):
    resp = _client().get(path)
    assert resp.status_code == 503
    assert "Coming Soon" in resp.text


@pytest.mark.parametrize(
    "path", ["/health", "/health/ready", "/login", "/coming-soon", "/t/open/1", "/static/x.css"]
)
def test_infrastructure_paths_stay_reachable(path):
    assert _client().get(path).status_code == 200


def test_license_is_reachable_without_a_preview_cookie():
    """Sample newsletters link here; recipients have no preview cookie."""
    resp = _client().get("/license")
    assert resp.status_code == 200
    assert "Coming Soon" not in resp.text


def test_preview_token_opens_the_gate_and_sets_a_cookie():
    client = _client()
    resp = client.get(f"/samples?preview={TOKEN}")
    assert resp.status_code == 200
    assert "_preview" in resp.cookies or "_preview" in client.cookies


def test_wrong_preview_token_stays_gated():
    assert _client().get("/samples?preview=wrong").status_code == 503


def test_gate_disabled_lets_everything_through():
    assert _client(enabled=False).get("/samples").status_code == 200


def test_authenticated_admin_bypasses_the_gate(monkeypatch):
    """A logged-in admin sees the real site while it is still hidden."""
    monkeypatch.setattr("weeklyamp.web.security.is_authenticated", lambda request: True)
    assert _client().get("/samples").status_code == 200


def test_advertise_is_reachable_without_a_preview_cookie():
    """Media kit is a CTA target in the samples, same as /license."""
    resp = _client().get("/advertise")
    assert resp.status_code == 200
    assert "Coming Soon" not in resp.text
