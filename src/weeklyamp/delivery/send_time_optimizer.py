"""Send-Time Optimization (STO) engine.

Analyses subscriber open-event timestamps from ``email_tracking_events``
and computes a per-subscriber preferred send hour.  The algorithm uses
mode-of-open-hours weighted by recency (90-day exponential decay).

All datetime parsing is done in Python to avoid SQLite/Postgres function
divergence.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# How many days back to consider (older events get exponential decay).
DECAY_WINDOW_DAYS = 90


def _parse_timestamp(ts) -> Optional[datetime]:
    """Parse a timestamp value from either SQLite (ISO string) or
    Postgres (datetime object) into a Python datetime.

    Returns None if parsing fails.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        # Try common ISO formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
        # Try with timezone info (strip it for simplicity)
        try:
            # Handle "+00:00" or "+00" suffix
            cleaned = ts.split("+")[0].split("Z")[0].strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    return datetime.strptime(cleaned, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
    return None


def _compute_weighted_hour(open_events: list[dict], now: Optional[datetime] = None) -> tuple[int, float, int]:
    """Compute the preferred hour from a list of open events.

    Uses recency-weighted mode: each event's hour gets a weight of
    ``exp(-age_days / DECAY_WINDOW_DAYS)``.  The hour with the highest
    total weight wins.

    Returns:
        (preferred_hour, confidence, sample_count)
        where confidence is in [0.0, 1.0] — higher means more concentrated
        opens in the preferred hour.
    """
    if now is None:
        now = datetime.utcnow()

    hour_weights: Counter[int] = Counter()
    sample_count = 0

    for event in open_events:
        ts = _parse_timestamp(event.get("created_at"))
        if ts is None:
            continue

        age_days = max((now - ts).total_seconds() / 86400, 0)
        weight = math.exp(-age_days / DECAY_WINDOW_DAYS)
        hour_weights[ts.hour] += weight
        sample_count += 1

    if sample_count == 0:
        return (9, 0.0, 0)  # default: 9 AM with zero confidence

    # Find the hour with the highest weight
    preferred_hour = hour_weights.most_common(1)[0][0]
    total_weight = sum(hour_weights.values())
    preferred_weight = hour_weights[preferred_hour]

    # Confidence = proportion of total weight in the preferred hour,
    # scaled by a sample-size factor (more samples = higher confidence)
    concentration = preferred_weight / total_weight if total_weight > 0 else 0
    sample_factor = min(sample_count / 10.0, 1.0)  # ramps up to 1.0 at 10 samples
    confidence = round(concentration * sample_factor, 3)

    return (preferred_hour, confidence, sample_count)


def compute_optimal_send_time(subscriber_id: int, repo) -> tuple[int, float, int]:
    """Query open events for a single subscriber and compute optimal send hour.

    Args:
        subscriber_id: The subscriber to analyse.
        repo: A Repository instance.

    Returns:
        (preferred_hour, confidence, sample_count)
    """
    events = repo.get_open_events_for_subscriber(subscriber_id)
    return _compute_weighted_hour(events)


def refresh_all_send_times(repo) -> int:
    """Batch-recompute optimal send times for all subscribers with open data.

    Returns the number of subscribers updated.
    """
    subscribers_with_opens = repo.get_all_subscribers_with_opens()
    updated = 0
    now = datetime.utcnow()

    for row in subscribers_with_opens:
        sub_id = row["subscriber_id"]
        events = repo.get_open_events_for_subscriber(sub_id)
        preferred_hour, confidence, sample_count = _compute_weighted_hour(events, now)

        if sample_count > 0:
            repo.upsert_subscriber_send_time(
                subscriber_id=sub_id,
                preferred_hour=preferred_hour,
                confidence=confidence,
                sample_count=sample_count,
            )
            updated += 1

    logger.info("STO refresh complete: %d subscribers updated", updated)
    return updated


def get_send_time_distribution(repo) -> list[dict]:
    """Return a histogram of subscriber counts by preferred hour.

    Each entry has: preferred_hour, subscriber_count, avg_confidence.
    Hours with zero subscribers are included for chart completeness.
    """
    stats = repo.get_send_time_stats()
    # Build a full 0-23 hour map
    hour_map = {h: {"preferred_hour": h, "subscriber_count": 0, "avg_confidence": 0.0} for h in range(24)}
    for row in stats:
        h = row["preferred_hour"]
        if 0 <= h <= 23:
            hour_map[h] = {
                "preferred_hour": h,
                "subscriber_count": row["subscriber_count"],
                "avg_confidence": row.get("avg_confidence", 0.0),
            }
    return [hour_map[h] for h in range(24)]
