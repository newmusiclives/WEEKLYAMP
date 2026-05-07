"""Tests for the locale fact-sheet loader, prompt builder, and auditor."""
from __future__ import annotations

import pytest

from weeklyamp.research.locale_facts import (
    audit_draft,
    build_writer_context,
    load_locale,
)


def test_load_locale_corrales():
    sheet = load_locale("corrales-nm")
    assert sheet["locale"]["name"] == "Corrales"
    assert any(v["name"] == "Casa Vieja" for v in sheet["venues"])
    assert any(d["name"] == "Corrales Bistro Brewery" for d in sheet["do_not_mention"])


def test_load_locale_missing():
    with pytest.raises(FileNotFoundError):
        load_locale("not-a-real-locale")


def test_writer_context_has_constraint_and_blocklist():
    ctx = build_writer_context("corrales-nm")
    assert "VERIFIED FACTS FOR CORRALES" in ctx
    assert "may reference ONLY" in ctx
    assert "Casa Vieja" in ctx
    assert "DO NOT MENTION" in ctx
    assert "Corrales Bistro Brewery" in ctx
    # Stepbridge should carry the post-production warning so the writer
    # doesn't pitch it as a music tracking room.
    assert "POST-PRODUCTION ONLY" in ctx


def test_audit_catches_blocked_entity():
    draft = "<p>Come hear the band at the Corrales Bistro Brewery on Friday.</p>"
    findings = audit_draft(draft, "corrales-nm")
    errors = [f for f in findings if f.severity == "error"]
    assert any("Bistro Brewery" in f.name for f in errors)


def test_audit_catches_fabricated_studio():
    draft = "<p>We tracked the EP at Empire Recording in the North Valley.</p>"
    findings = audit_draft(draft, "corrales-nm")
    errors = [f for f in findings if f.severity == "error"]
    assert any(f.name == "Empire Recording" for f in errors)


def test_audit_passes_verified_only_draft():
    draft = (
        "<p>Casa Vieja and Sister Bar are both worth a Friday night. "
        "Music in Corrales runs at the Historic Old San Ysidro Church.</p>"
    )
    findings = audit_draft(draft, "corrales-nm")
    errors = [f for f in findings if f.severity == "error"]
    assert errors == []


def test_audit_flags_unknown_studio_as_warning():
    draft = "<p>We're tracking next month at Bogus Studios in Albuquerque.</p>"
    findings = audit_draft(draft, "corrales-nm")
    warns = [f for f in findings if f.severity == "warn" and f.kind == "unknown_entity"]
    assert any(f.name == "Bogus Studios" for f in warns)
