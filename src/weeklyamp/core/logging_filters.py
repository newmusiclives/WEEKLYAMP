"""PII redaction for application logs.

Wired into the root logger at app startup so every log record gets
sensitive substrings replaced before it leaves the process. Covers the
three leakage vectors we see most often in a Python/FastAPI stack:

1. Email addresses appearing in log messages (subscriber actions, error
   traces that include form payloads, etc.).
2. North American and international phone numbers.
3. Bearer tokens / API keys that slip into a log line via ``%s``
   formatting of request headers.

Sentry has its own PII scrubber (``send_default_pii=False``), but the
Railway stdout logs are our primary observability today and those are
in-process ``logging`` records — so we need this filter too.
"""

from __future__ import annotations

import logging
import re

# Conservative — targets obvious PII without trying to redact every
# possible identifier. False positives (e.g. redacting a version string
# that looks like an email) are acceptable; false negatives are not.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<![\w\d])(\+?\d{1,3}[\s.-]?)?"     # optional country code
    r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"  # 3-3-4 grouping
    r"(?!\w)"
)
_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-+/=]{6,}", re.IGNORECASE)
_TFS_KEY_RE = re.compile(r"tfs_[A-Za-z0-9_\-]{16,}")


def _redact(text: str) -> str:
    text = _BEARER_RE.sub(r"\1<redacted>", text)
    text = _TFS_KEY_RE.sub("<redacted-api-key>", text)
    text = _EMAIL_RE.sub("<redacted-email>", text)
    text = _PHONE_RE.sub("<redacted-phone>", text)
    return text


class PIIRedactionFilter(logging.Filter):
    """logging.Filter that rewrites msg + args to redact PII.

    Applied to the root logger so every child logger inherits the
    redaction without having to opt in. Works on both ``%s``-formatted
    and pre-formatted messages.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # If args are present, format first so we see the full
            # message the user would have seen, then rewrite from
            # scratch. Otherwise rewrite msg in place.
            if record.args:
                try:
                    formatted = record.msg % record.args
                except (TypeError, ValueError):
                    formatted = str(record.msg)
                record.msg = _redact(formatted)
                record.args = None
            elif isinstance(record.msg, str):
                record.msg = _redact(record.msg)
        except Exception:
            # Never let the filter raise — that would silence the log.
            pass
        return True


def install() -> None:
    """Attach the PII filter to every handler on the root logger.

    Important: filters attached to a Logger only fire for records
    emitted AT that logger — they do not propagate down to child
    loggers. Filters attached to a Handler fire for every record that
    reaches it, including propagated records from child loggers. So
    we walk the root's handlers and attach to each. Idempotent.
    """
    filt = PIIRedactionFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        if any(isinstance(f, PIIRedactionFilter) for f in handler.filters):
            continue
        handler.addFilter(filt)
