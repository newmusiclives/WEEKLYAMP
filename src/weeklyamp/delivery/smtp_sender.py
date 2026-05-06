"""SMTP email sender for newsletter delivery via GoHighLevel / Mailgun."""

from __future__ import annotations

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Optional, Tuple

from weeklyamp.core.models import EmailConfig

logger = logging.getLogger(__name__)

# Per-recipient HTML/plain producer. Returns (html, plain). Either field
# may be empty to fall back to the bulk-send defaults.
Personalizer = Callable[[dict], Tuple[str, str]]

# Send in batches to avoid SMTP connection limits
_BATCH_SIZE = 50
_BATCH_DELAY = 1.0  # seconds between batches


def _retry_with_backoff(fn, max_attempts=3, backoff_delays=(1, 2, 4)):
    """Call fn(), retrying on SMTPException/ConnectionError with backoff."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except (smtplib.SMTPException, ConnectionError, OSError) as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                logger.warning("SMTP attempt %d/%d failed (%s), retrying in %ds", attempt + 1, max_attempts, exc, delay)
                time.sleep(delay)
    raise last_exc


class SMTPSender:
    """Send newsletters via SMTP (GoHighLevel / Mailgun)."""

    def __init__(self, config: EmailConfig, warmup_config=None) -> None:
        self.config = config
        self._warmup_config = warmup_config

    def _build_message(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_text: str = "",
        unsubscribe_url: str = "",
    ) -> MIMEMultipart:
        """Build a MIME email message."""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.config.from_name} <{self.config.from_address}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # List-Unsubscribe header for one-click unsubscribe
        if unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Plain text version (fallback)
        if plain_text:
            msg.attach(MIMEText(plain_text, "plain", "utf-8"))

        # HTML version
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        return msg

    def send_single(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_text: str = "",
        unsubscribe_url: str = "",
    ) -> bool:
        """Send a single email. Returns True on success."""
        if not self.config.enabled:
            logger.warning("Email sending is disabled")
            return False

        msg = self._build_message(to_email, subject, html_body, plain_text, unsubscribe_url)

        def _do_send():
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

        try:
            _retry_with_backoff(_do_send)
            logger.info("Email sent to %s", to_email)
            return True
        except Exception:
            logger.exception("Failed to send email to %s after retries", to_email)
            return False

    def send_bulk(
        self,
        recipients: list[dict],
        subject: str,
        html_body: str,
        plain_text: str = "",
        site_domain: str = "",
        *,
        personalize: "Personalizer | None" = None,
    ) -> dict:
        """Send newsletter to a list of recipients via SMTP.

        Args:
            recipients: list of {"id": int, "email": str, "unsubscribe_token": str, ...}
            subject: Email subject line
            html_body: Full newsletter HTML — used when ``personalize``
                is None or returns falsy for a recipient.
            plain_text: Plain text version (same fallback semantics).
            site_domain: Base URL for unsubscribe links.
            personalize: Optional callable taking a recipient dict and
                returning ``(html, plain)`` for that recipient. Used by
                callers that want per-subscriber section ranking — see
                :func:`weeklyamp.content.assembly.assemble_newsletter`'s
                ``subscriber_id`` param. Falling back to the static
                ``html_body`` on a None/empty return keeps the loop
                resilient: a single subscriber's personalization
                failure does not abort the batch.

        Returns: {"sent": N, "failed": N, "errors": [...]}
        """
        if not self.config.enabled:
            logger.warning("Email sending is disabled")
            return {"sent": 0, "failed": 0, "errors": ["Email sending is disabled"]}

        # Domain warm-up: respect daily limit if enabled
        if self._warmup_config and getattr(self._warmup_config, 'warmup_enabled', False):
            from weeklyamp.delivery.warmup import WarmupManager
            warmup = WarmupManager(None, self._warmup_config)  # repo not needed for limit calc
            daily_limit = self._warmup_config.warmup_daily_start
            if daily_limit and len(recipients) > daily_limit:
                logger.info("Warm-up active: limiting recipients from %d to %d", len(recipients), daily_limit)
                recipients = recipients[:daily_limit]

        sent = 0
        failed = 0
        errors: list[str] = []

        for batch_start in range(0, len(recipients), _BATCH_SIZE):
            batch = recipients[batch_start:batch_start + _BATCH_SIZE]

            try:
                def _connect():
                    server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                    server.starttls()
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    return server

                server = _retry_with_backoff(_connect)
                try:
                    for recipient in batch:
                        email = recipient.get("email", "")
                        if not email:
                            continue

                        # Build per-recipient unsubscribe URL
                        unsub_token = recipient.get("unsubscribe_token", "")
                        unsub_url = ""
                        if unsub_token and site_domain:
                            unsub_url = f"{site_domain.rstrip('/')}/unsubscribe?token={unsub_token}"

                        # Resolve the per-recipient HTML. If a personalizer
                        # is supplied (per-subscriber section ranking),
                        # call it; on any failure or empty return, fall
                        # back to the bulk html_body so one bad subscriber
                        # doesn't break the batch.
                        recipient_html = html_body
                        recipient_plain = plain_text
                        if personalize is not None:
                            try:
                                p_html, p_plain = personalize(recipient)
                                if p_html:
                                    recipient_html = p_html
                                if p_plain:
                                    recipient_plain = p_plain
                            except Exception:
                                logger.exception(
                                    "Personalizer raised for %s — using bulk HTML", email,
                                )

                        # Personalize HTML with unsubscribe link
                        personalized_html = recipient_html.replace(
                            "{{ unsubscribe_url }}", unsub_url or "#"
                        )

                        msg = self._build_message(
                            to_email=email,
                            subject=subject,
                            html_body=personalized_html,
                            plain_text=recipient_plain,
                            unsubscribe_url=unsub_url,
                        )

                        try:
                            server.send_message(msg)
                            sent += 1
                        except Exception as e:
                            failed += 1
                            errors.append(f"{email}: {e}")
                            logger.warning("Failed to send to %s: %s", email, e)
                finally:
                    server.quit()

            except Exception as e:
                # Connection-level failure — count remaining batch as failed
                failed += len(batch)
                errors.append(f"SMTP connection error: {e}")
                logger.exception("SMTP connection failed for batch starting at %d", batch_start)

            # Pause between batches to respect rate limits
            if batch_start + _BATCH_SIZE < len(recipients):
                time.sleep(_BATCH_DELAY)

        logger.info("Bulk send complete: %d sent, %d failed out of %d", sent, failed, len(recipients))
        return {"sent": sent, "failed": failed, "errors": errors}
