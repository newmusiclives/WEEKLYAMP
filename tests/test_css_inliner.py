"""Tests for CSS inlining in email delivery."""

from unittest.mock import MagicMock, patch
import pytest


def test_inline_css_moves_styles_to_inline():
    """Test that <style> block rules become inline style attributes."""
    from weeklyamp.delivery.css_inliner import inline_css

    html = """<html><head><style>
    .headline { color: red; font-size: 24px; }
    p { margin: 10px; }
    </style></head><body>
    <h1 class="headline">Hello</h1>
    <p>World</p>
    </body></html>"""

    result = inline_css(html)

    # Style attributes should be inlined
    assert 'style="' in result
    assert "color: red" in result or "color:red" in result
    # Classes should be preserved (remove_classes=False)
    assert 'class="headline"' in result
    # The <style> block should be removed (keep_style_tags=False)
    assert "<style>" not in result


def test_inline_css_preserves_existing_inline_styles():
    """Test that existing inline styles are kept and merged."""
    from weeklyamp.delivery.css_inliner import inline_css

    html = """<html><head><style>
    p { color: blue; }
    </style></head><body>
    <p style="font-weight: bold;">Hello</p>
    </body></html>"""

    result = inline_css(html)
    assert "font-weight" in result
    assert "color" in result


def test_inline_css_empty_input():
    """Test that empty/falsy input passes through unchanged."""
    from weeklyamp.delivery.css_inliner import inline_css

    assert inline_css("") == ""
    assert inline_css(None) is None


def test_inline_css_no_style_block():
    """Test HTML without <style> tags passes through cleanly."""
    from weeklyamp.delivery.css_inliner import inline_css

    html = "<html><body><p>No styles here</p></body></html>"
    result = inline_css(html)
    assert "No styles here" in result


def test_inline_css_graceful_on_import_error():
    """Test graceful fallback when premailer is not installed."""
    from weeklyamp.delivery.css_inliner import inline_css

    original = "<html><head><style>p{color:red}</style></head><body><p>Hi</p></body></html>"

    with patch.dict("sys.modules", {"premailer": None}):
        # Force reimport to trigger ImportError path
        import importlib
        import weeklyamp.delivery.css_inliner as mod
        importlib.reload(mod)
        result = mod.inline_css(original)

    assert result == original


def test_inline_css_graceful_on_transform_error():
    """Test graceful fallback when premailer.transform raises."""
    from weeklyamp.delivery.css_inliner import inline_css

    original = "<html><body><p>Hi</p></body></html>"

    with patch("premailer.transform", side_effect=ValueError("bad html")):
        result = inline_css(original)

    assert result == original


def test_inline_css_handles_jinja_placeholders():
    """Test that Jinja template placeholders survive inlining."""
    from weeklyamp.delivery.css_inliner import inline_css

    html = """<html><head><style>
    .cta { background: #1a1a1a; }
    </style></head><body>
    <a class="cta" href="{{ unsubscribe_url }}">Unsubscribe</a>
    </body></html>"""

    result = inline_css(html)
    # The Jinja placeholder should survive (premailer doesn't touch href values)
    assert "{{ unsubscribe_url }}" in result or "{{" in result


def test_inline_css_handles_complex_newsletter_html():
    """Test inlining on a realistic newsletter HTML structure."""
    from weeklyamp.delivery.css_inliner import inline_css

    html = """<!DOCTYPE html>
<html>
<head>
<style>
body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }
.container { max-width: 600px; margin: 0 auto; background: #ffffff; }
.header { background: #1a1a1a; color: #ffffff; padding: 20px; text-align: center; }
.section { padding: 20px; border-bottom: 1px solid #eee; }
.section h2 { color: #1a1a1a; font-size: 20px; }
.section p { color: #333; line-height: 1.6; }
.footer { padding: 16px; text-align: center; font-size: 12px; color: #999; }
.btn { display: inline-block; padding: 12px 24px; background: #2563eb; color: #fff; text-decoration: none; border-radius: 6px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>DISPATCH Weekly</h1>
  </div>
  <div class="section">
    <h2>This Week in Music</h2>
    <p>Breaking news and analysis from across the industry.</p>
    <a class="btn" href="https://example.com">Read More</a>
  </div>
  <div class="footer">
    <p>You received this because you subscribed.</p>
    <a href="{{ unsubscribe_url }}">Unsubscribe</a>
  </div>
</div>
</body>
</html>"""

    result = inline_css(html)

    # Styles should be inlined
    assert "<style>" not in result
    assert 'style="' in result
    # Content must survive
    assert "DISPATCH Weekly" in result
    assert "This Week in Music" in result
    assert "Read More" in result
    assert "Unsubscribe" in result


def test_smtp_sender_inlines_css_on_send_single():
    """Test that SMTPSender.send_single inlines CSS before sending."""
    from weeklyamp.delivery.smtp_sender import SMTPSender
    from weeklyamp.core.models import EmailConfig

    config = EmailConfig(
        enabled=True,
        smtp_host="localhost",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
        from_address="test@example.com",
        from_name="Test",
    )
    sender = SMTPSender(config)

    captured_msg = {}

    def fake_send():
        pass

    with patch("weeklyamp.delivery.smtp_sender._retry_with_backoff") as mock_retry:
        with patch("weeklyamp.delivery.smtp_sender.inline_css") as mock_inline:
            mock_inline.return_value = "<p style='color:red'>Inlined</p>"
            # Make _retry_with_backoff just call the function
            mock_retry.side_effect = lambda fn, **kw: fn()

            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = mock_smtp.return_value.__enter__.return_value
                mock_server.send_message = lambda msg: captured_msg.update({"sent": True})

                sender.send_single("to@test.com", "Test", "<style>p{color:red}</style><p>Hi</p>")

            # inline_css should have been called with the original HTML
            mock_inline.assert_called_once_with("<style>p{color:red}</style><p>Hi</p>")


def test_smtp_sender_inlines_css_on_send_bulk():
    """Test that SMTPSender.send_bulk inlines CSS on the bulk HTML."""
    from weeklyamp.delivery.smtp_sender import SMTPSender
    from weeklyamp.core.models import EmailConfig

    config = EmailConfig(
        enabled=True,
        smtp_host="localhost",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
        from_address="test@example.com",
        from_name="Test",
    )
    sender = SMTPSender(config)

    with patch("weeklyamp.delivery.smtp_sender.inline_css") as mock_inline:
        mock_inline.return_value = "<p style='color:red'>Inlined</p>"
        with patch("weeklyamp.delivery.smtp_sender._retry_with_backoff") as mock_retry:
            mock_server = MagicMock()
            mock_retry.return_value = mock_server
            sender.send_bulk(
                [{"email": "a@test.com"}],
                "Subject",
                "<style>p{color:red}</style><p>Hi</p>",
            )
        mock_inline.assert_called_once_with("<style>p{color:red}</style><p>Hi</p>")
