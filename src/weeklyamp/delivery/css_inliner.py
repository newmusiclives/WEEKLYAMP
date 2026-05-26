"""Inline CSS styles for email compatibility."""

import logging

logger = logging.getLogger(__name__)


def inline_css(html: str) -> str:
    """Move CSS from <style> blocks into inline style attributes.

    This ensures consistent rendering across email clients (Outlook,
    Gmail, Yahoo) that strip <style> tags.

    Gracefully degrades: returns the original HTML unchanged if
    ``premailer`` is not installed or if transformation fails.
    """
    if not html:
        return html

    try:
        import premailer

        return premailer.transform(
            html,
            remove_classes=False,
            strip_important=False,
            keep_style_tags=False,
            cssutils_logging_level=logging.CRITICAL,
        )
    except ImportError:
        logger.warning("premailer not installed — skipping CSS inlining")
        return html
    except Exception:
        logger.exception("CSS inlining failed — sending with original styles")
        return html
