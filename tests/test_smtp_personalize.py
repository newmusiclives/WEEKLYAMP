"""Tests for the SMTPSender personalizer hook.

Asserts the per-subscriber HTML override path used by the genre/engagement
ranker. We don't actually open SMTP connections — `smtplib.SMTP` is
patched so the test exercises only our loop behaviour.

Properties under test:
  1. With no personalizer, every recipient receives the bulk html_body.
  2. With a personalizer, each recipient receives the personalizer's
     output for their row.
  3. A personalizer that raises does NOT abort the batch — the
     recipient gets the bulk fallback and other recipients still send.
  4. A personalizer that returns ("", "") falls back to the bulk HTML
     for that one recipient (used as an "I have nothing custom for
     this person" signal).
  5. The unsubscribe_url placeholder substitution still happens on
     personalized HTML, not just the bulk one.
"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch

import pytest

from weeklyamp.core.models import EmailConfig
from weeklyamp.delivery.smtp_sender import SMTPSender


@pytest.fixture()
def email_config():
    """Enabled config with throwaway SMTP creds — connection is mocked."""
    return EmailConfig(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
        from_address="newsletter@example.com",
        from_name="DISPATCH",
    )


@pytest.fixture()
def captured_messages():
    """List that the mocked server.send_message appends to so tests can
    introspect what the loop actually queued."""
    return []


@pytest.fixture()
def mock_smtp(captured_messages):
    """Replace smtplib.SMTP with a MagicMock that records every
    send_message call's MIMEMultipart payload. Yields the captured list."""
    server = MagicMock()
    def _capture(msg: MIMEMultipart):
        captured_messages.append(msg)
    server.send_message.side_effect = _capture

    with patch("weeklyamp.delivery.smtp_sender.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value = server
        yield smtp_cls


def _html_payload(msg: MIMEMultipart) -> str:
    """Extract the text/html part of a multipart message."""
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode()
    raise AssertionError("No html part in message")


def test_no_personalizer_uses_bulk_html(email_config, mock_smtp, captured_messages):
    sender = SMTPSender(email_config)
    recipients = [
        {"id": 1, "email": "a@example.com", "unsubscribe_token": "tok-a"},
        {"id": 2, "email": "b@example.com", "unsubscribe_token": "tok-b"},
    ]
    result = sender.send_bulk(
        recipients=recipients,
        subject="Test",
        html_body="<p>Bulk HTML</p>",
        plain_text="Bulk plain",
        site_domain="https://x.example",
    )
    assert result["sent"] == 2
    assert result["failed"] == 0
    for msg in captured_messages:
        assert "Bulk HTML" in _html_payload(msg)


def test_personalizer_overrides_html_per_recipient(email_config, mock_smtp, captured_messages):
    sender = SMTPSender(email_config)
    recipients = [
        {"id": 1, "email": "a@example.com", "unsubscribe_token": "tok-a"},
        {"id": 2, "email": "b@example.com", "unsubscribe_token": "tok-b"},
    ]

    def personalize(rec: dict) -> tuple[str, str]:
        return f"<p>HTML for {rec['email']}</p>", f"plain for {rec['email']}"

    sender.send_bulk(
        recipients=recipients,
        subject="Test",
        html_body="<p>Bulk HTML</p>",
        plain_text="Bulk plain",
        site_domain="https://x.example",
        personalize=personalize,
    )
    htmls = [_html_payload(m) for m in captured_messages]
    assert any("HTML for a@example.com" in h for h in htmls)
    assert any("HTML for b@example.com" in h for h in htmls)
    # And the bulk html is NOT the one that went out
    assert not any(h == "<p>Bulk HTML</p>" for h in htmls)


def test_personalizer_exception_falls_back_to_bulk(email_config, mock_smtp, captured_messages):
    """A single subscriber's personalization failure must not abort the
    batch. The bulk HTML is sent for that one recipient, and other
    recipients are unaffected. This is the safety property that lets
    operators turn the feature on without auditing every code path
    inside their personalizer."""
    sender = SMTPSender(email_config)
    recipients = [
        {"id": 1, "email": "ok@example.com", "unsubscribe_token": "tok-ok"},
        {"id": 2, "email": "boom@example.com", "unsubscribe_token": "tok-boom"},
    ]

    def personalize(rec: dict) -> tuple[str, str]:
        if rec["email"] == "boom@example.com":
            raise RuntimeError("rendering blew up")
        return f"<p>HTML for {rec['email']}</p>", ""

    result = sender.send_bulk(
        recipients=recipients,
        subject="Test",
        html_body="<p>Bulk HTML</p>",
        plain_text="Bulk plain",
        site_domain="https://x.example",
        personalize=personalize,
    )
    # Both still sent — boom got the bulk fallback
    assert result["sent"] == 2
    htmls = [_html_payload(m) for m in captured_messages]
    assert any("HTML for ok@example.com" in h for h in htmls)
    assert any("Bulk HTML" in h for h in htmls)


def test_personalizer_empty_return_falls_back_to_bulk(email_config, mock_smtp, captured_messages):
    """Returning ("", "") is the personalizer's way of saying "no
    custom version for this recipient" — the bulk HTML should be used."""
    sender = SMTPSender(email_config)
    recipients = [{"id": 1, "email": "a@example.com", "unsubscribe_token": "t"}]

    def personalize(rec: dict) -> tuple[str, str]:
        return "", ""

    sender.send_bulk(
        recipients=recipients, subject="Test",
        html_body="<p>Bulk HTML</p>", plain_text="Bulk plain",
        site_domain="https://x.example", personalize=personalize,
    )
    assert "Bulk HTML" in _html_payload(captured_messages[0])


def test_unsubscribe_token_substituted_in_personalized_html(email_config, mock_smtp, captured_messages):
    """The unsub-link substitution runs AFTER personalization. A
    personalizer that emits the {{ unsubscribe_url }} placeholder must
    still get a real link in the final email."""
    sender = SMTPSender(email_config)
    recipients = [{"id": 1, "email": "a@example.com", "unsubscribe_token": "secrettok"}]

    def personalize(rec: dict) -> tuple[str, str]:
        return '<p>Custom <a href="{{ unsubscribe_url }}">unsub</a></p>', ""

    sender.send_bulk(
        recipients=recipients, subject="Test",
        html_body="<p>Bulk</p>", plain_text="",
        site_domain="https://x.example", personalize=personalize,
    )
    html = _html_payload(captured_messages[0])
    assert "https://x.example/unsubscribe?token=secrettok" in html
    assert "{{ unsubscribe_url }}" not in html
