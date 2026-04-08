"""Tests for the pre-send preflight checklist."""

from __future__ import annotations

from weeklyamp.delivery.preflight import (
    check_html_body,
    check_plain_text,
    check_recipients,
    check_subject,
    run_preflight,
)


def _severities(issues):
    return [s for s, _ in issues]


def test_subject_empty_blocks():
    assert _severities(check_subject("")) == ["block"]


def test_subject_short_warns():
    sevs = _severities(check_subject("Hi there"))
    assert "warn" in sevs


def test_subject_long_warns():
    sevs = _severities(check_subject("x" * 100))
    assert "warn" in sevs


def test_subject_all_caps_warns():
    sevs = _severities(check_subject("THIS IS A SHOUTY SUBJECT LINE NOW"))
    assert "warn" in sevs


def test_subject_spam_punctuation_warns():
    sevs = _severities(check_subject("Free music inside!!!"))
    assert "warn" in sevs


def test_subject_normal_passes():
    assert check_subject("Your weekly dose of music industry news") == []


def test_html_empty_blocks():
    sevs = _severities(check_html_body(""))
    assert "block" in sevs


def test_html_missing_unsubscribe_blocks():
    sevs = _severities(check_html_body("<p>hello world</p>"))
    assert "block" in sevs


def test_html_with_unsubscribe_passes():
    html = '<p>hello</p><a href="/unsubscribe?token=abc">Unsubscribe</a>'
    assert check_html_body(html) == []


def test_html_empty_href_warns():
    html = '<a href="">click</a><p>unsubscribe link</p>'
    sevs = _severities(check_html_body(html))
    assert "warn" in sevs


def test_html_image_without_alt_warns():
    html = '<img src="/x.png"><p>unsubscribe</p>'
    sevs = _severities(check_html_body(html))
    assert "warn" in sevs


def test_html_image_with_alt_passes():
    html = '<img src="/x.png" alt="logo"><p>unsubscribe</p>'
    assert check_html_body(html) == []


def test_plain_text_empty_warns():
    sevs = _severities(check_plain_text(""))
    assert "warn" in sevs


def test_plain_text_too_short_warns():
    sevs = _severities(check_plain_text("hi"))
    assert "warn" in sevs


def test_plain_text_long_enough_passes():
    assert check_plain_text("x" * 250) == []


def test_recipients_empty_blocks():
    sevs = _severities(check_recipients([]))
    assert "block" in sevs


def test_run_preflight_happy_path():
    result = run_preflight(
        subject="Your weekly music industry digest",
        html_body='<p>Hello world</p><a href="/unsubscribe?token=x">Unsubscribe</a>',
        plain_text="Hello world. " * 30,
        recipients=[{"email": "a@b.com"}],
    )
    assert result["ok"] is True
    assert result["blockers"] == []


def test_run_preflight_blocks_on_missing_unsubscribe():
    result = run_preflight(
        subject="Your weekly music industry digest",
        html_body="<p>No unsub link here</p>",
        plain_text="Hello world. " * 30,
        recipients=[{"email": "a@b.com"}],
    )
    assert result["ok"] is False
    assert any("unsubscribe" in b.lower() for b in result["blockers"])
