"""Tests for email template rendering and XSS sanitisation."""

from __future__ import annotations

import pytest

from weeklyamp.delivery.templates import (
    render_guest_section,
    render_newsletter,
    render_sponsor_block,
    render_submission_section,
)
from weeklyamp.web.sanitize import sanitize_html


# ---- render_newsletter ----

def test_render_newsletter_produces_valid_html():
    html = render_newsletter(
        newsletter_name="TestNews",
        tagline="Test tagline",
        issue_number=42,
        title="Test Issue",
        sections=[{"html": "<p>Hello world</p>"}],
        css="body { color: red; }",
    )
    assert "<!DOCTYPE html>" in html
    assert "TestNews" in html
    assert "Issue #42" in html or "#42" in html
    assert "<p>Hello world</p>" in html


def test_render_newsletter_with_empty_sections():
    html = render_newsletter(
        newsletter_name="EmptyTest",
        tagline="",
        issue_number=1,
        title="Empty",
        sections=[],
    )
    assert "<!DOCTYPE html>" in html
    assert "EmptyTest" in html


def test_render_newsletter_includes_footer():
    html = render_newsletter(
        newsletter_name="Footer",
        tagline="",
        issue_number=1,
        title="",
        sections=[],
        footer_html="<p>Custom footer</p>",
    )
    assert "Custom footer" in html


# ---- render_guest_section XSS ----

def test_render_guest_section_sanitizes_xss_in_author_bio():
    html = render_guest_section(
        content_html="<p>Safe content</p>",
        author_name="Guest Author",
        author_bio='<script>alert("xss")</script><b>Bio text</b>',
    )
    assert "<script>" not in html
    # bleach strips the script tag but keeps inner text; the key is no executable tag
    assert "<b>Bio text</b>" in html
    assert "Guest Author" in html


def test_render_guest_section_sanitizes_xss_in_author_name():
    html = render_guest_section(
        content_html="<p>Content</p>",
        author_name='<img src=x onerror=alert(1)>Bob',
    )
    # The onerror attribute should be stripped
    assert "onerror" not in html


def test_render_guest_section_sanitizes_content():
    html = render_guest_section(
        content_html='<p>OK</p><script>document.cookie</script>',
        author_name="Safe",
    )
    assert "<script>" not in html
    assert "<p>OK</p>" in html


# ---- render_submission_section XSS ----

def test_render_submission_section_sanitizes_xss_in_artist_social():
    html = render_submission_section(
        content_html="<p>Music review</p>",
        artist_name="Test Artist",
        artist_social='<script>steal()</script>@testartist',
    )
    assert "<script>" not in html
    assert "@testartist" in html


def test_render_submission_section_sanitizes_content():
    html = render_submission_section(
        content_html='<div onclick="evil()">Click</div><p>Safe</p>',
        artist_name="Artist",
    )
    assert "onclick" not in html
    assert "<p>Safe</p>" in html


# ---- render_sponsor_block XSS ----

def test_render_sponsor_block_sanitizes_xss_in_body_html():
    html = render_sponsor_block({
        "sponsor_name": "Acme Corp",
        "headline": "Great Product",
        "body_html": '<p>Check it out</p><script>alert("xss")</script>',
        "cta_url": "https://example.com",
        "cta_text": "Learn More",
    })
    assert "<script>" not in html
    assert "<p>Check it out</p>" in html
    assert "Acme Corp" in html


def test_render_sponsor_block_sanitizes_xss_in_headline():
    html = render_sponsor_block({
        "sponsor_name": "Safe",
        "headline": '<img src=x onerror="alert(1)">Title',
        "body_html": "<p>Body</p>",
    })
    assert "onerror" not in html


def test_render_sponsor_block_with_empty_body():
    html = render_sponsor_block({
        "sponsor_name": "Minimal",
        "headline": "",
        "body_html": "",
        "cta_url": "",
    })
    assert "Minimal" in html


# ---- sanitize_html directly ----

def test_sanitize_html_strips_script_tags():
    result = sanitize_html('<p>Hello</p><script>alert("bad")</script>')
    assert "<script>" not in result
    assert "</script>" not in result
    # bleach with strip=True removes the tag but keeps inner text content;
    # the important thing is the <script> element itself is gone
    assert "<p>Hello</p>" in result


def test_sanitize_html_keeps_safe_tags():
    safe = "<p>Paragraph</p><strong>Bold</strong><em>Italic</em><a href=\"https://example.com\">Link</a>"
    result = sanitize_html(safe)
    assert "<p>" in result
    assert "<strong>" in result
    assert "<em>" in result
    assert "<a " in result


def test_sanitize_html_strips_event_handlers():
    result = sanitize_html('<div onclick="alert(1)">Click</div>')
    assert "onclick" not in result


def test_sanitize_html_strips_javascript_urls():
    result = sanitize_html('<a href="javascript:alert(1)">Link</a>')
    assert "javascript:" not in result


def test_sanitize_html_allows_img_with_safe_attrs():
    result = sanitize_html('<img src="https://img.com/pic.jpg" alt="photo">')
    assert "<img" in result
    assert 'src="https://img.com/pic.jpg"' in result
    assert 'alt="photo"' in result


def test_sanitize_html_strips_iframe():
    result = sanitize_html('<iframe src="https://evil.com"></iframe>')
    assert "<iframe" not in result


def test_sanitize_html_strips_style_tag():
    result = sanitize_html('<style>body{display:none}</style><p>Visible</p>')
    assert "<style>" not in result
    assert "<p>Visible</p>" in result
