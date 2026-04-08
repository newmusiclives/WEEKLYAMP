"""Pre-send checklist for newsletter issues.

Runs cheap, fast checks against an assembled issue before it's pushed
to subscribers. Catches the highest-frequency self-inflicted send
mistakes (subject too long, missing unsubscribe link, broken alt
text) without contacting external services. The HTTP-level link
checking and spam-score lookups are deferred to a separate background
job — preflight must be fast enough to run on every send click.

Returns a list of (severity, message) tuples. Severities:
    "block"  — must be fixed before sending
    "warn"   — non-blocking but flagged in the UI
"""

from __future__ import annotations

import re
from typing import Iterable

# Cheap regex-based extractors. Not perfect HTML parsers but fine for
# the assembled output we control end-to-end.
_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ALT_RE = re.compile(r'\balt\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)


def check_subject(subject: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if not subject:
        issues.append(("block", "Subject line is empty."))
        return issues
    n = len(subject)
    if n < 20:
        issues.append(("warn", f"Subject is short ({n} chars). 30-60 is the sweet spot."))
    elif n > 80:
        issues.append(("warn", f"Subject is long ({n} chars). Mobile clients truncate around 60."))
    # Spam-trigger heuristics — uppercase ratio, "FREE!!!", etc.
    upper = sum(1 for c in subject if c.isupper())
    if n >= 10 and (upper / n) > 0.5:
        issues.append(("warn", "Subject is more than half uppercase — looks like spam."))
    if subject.count("!") >= 3 or "$$$" in subject or "!!" in subject:
        issues.append(("warn", "Subject contains spam-trigger punctuation (!!, $$$)."))
    return issues


def check_html_body(html: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if not html or not html.strip():
        issues.append(("block", "HTML body is empty."))
        return issues

    lower = html.lower()

    # Unsubscribe link is legally required (CAN-SPAM, GDPR)
    if "unsubscribe" not in lower:
        issues.append(("block", "No unsubscribe link found in HTML body — CAN-SPAM violation."))

    # Broken hrefs (empty or pure '#')
    hrefs = _HREF_RE.findall(html)
    bad = [h for h in hrefs if not h.strip() or h.strip() == "#"]
    if bad:
        issues.append((
            "warn",
            f"{len(bad)} link(s) have empty or '#' href — likely placeholder.",
        ))

    # Images without alt text — accessibility + spam-score lift
    images = _IMG_RE.findall(html)
    no_alt = [img for img in images if not _ALT_RE.search(img)]
    if no_alt:
        issues.append((
            "warn",
            f"{len(no_alt)} image(s) missing alt text — accessibility + spam score impact.",
        ))

    # HTML-only with no plain-text equivalent is a deliverability red flag,
    # but the assemble step always produces plain text alongside HTML so
    # we leave that check to check_plain_text below.
    return issues


def check_plain_text(plain: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if not plain or not plain.strip():
        issues.append((
            "warn",
            "Plain-text version is missing — Gmail and others penalise HTML-only sends.",
        ))
        return issues
    if len(plain.strip()) < 200:
        issues.append((
            "warn",
            f"Plain-text version is very short ({len(plain.strip())} chars) — possible mismatch with HTML.",
        ))
    return issues


def check_recipients(recipients: Iterable[dict]) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    rs = list(recipients)
    if not rs:
        issues.append(("block", "Recipient list is empty — no one would receive this send."))
    elif len(rs) > 50000:
        issues.append((
            "warn",
            f"Recipient list is very large ({len(rs)}). Consider warm-up batching.",
        ))
    return issues


def run_preflight(
    *,
    subject: str,
    html_body: str,
    plain_text: str = "",
    recipients: Iterable[dict] | None = None,
) -> dict:
    """Run all preflight checks. Returns dict with `blockers`, `warnings`, `ok`."""
    all_issues: list[tuple[str, str]] = []
    all_issues.extend(check_subject(subject))
    all_issues.extend(check_html_body(html_body))
    all_issues.extend(check_plain_text(plain_text))
    if recipients is not None:
        all_issues.extend(check_recipients(recipients))

    blockers = [m for sev, m in all_issues if sev == "block"]
    warnings = [m for sev, m in all_issues if sev == "warn"]
    return {
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }
