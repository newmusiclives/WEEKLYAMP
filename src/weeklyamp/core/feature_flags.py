"""Lightweight feature flag system.

Flags are resolved in this precedence order:

1. Environment variable ``WEEKLYAMP_FF_<NAME>`` — highest priority so
   production can flip flags instantly via Railway without a deploy.
2. A row in the ``feature_flags`` table, with an optional
   ``rollout_percent`` for percentage rollouts keyed on an arbitrary
   identity string (subscriber_id, licensee_id, etc.).
3. The default passed to the ``enabled`` call.

This intentionally avoids a third-party SaaS (LaunchDarkly, Unleash)
for the pilot phase — the requirements are low and the operational
simplicity of a DB row + env var is worth more than the features of
a full platform. Can be swapped out cleanly later if needed.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_ENV_PREFIX = "WEEKLYAMP_FF_"


def _env_value(name: str) -> Optional[bool]:
    """Return True/False if the env override is set, else None."""
    raw = os.environ.get(f"{_ENV_PREFIX}{name.upper()}")
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _rollout_bucket(identity: str, flag_name: str) -> int:
    """Return a stable 0-99 bucket for (identity, flag). Same inputs → same
    bucket, so a subscriber either always sees the feature or never
    sees it (no flicker) until the rollout_percent is changed."""
    h = hashlib.sha1(f"{flag_name}:{identity}".encode()).hexdigest()
    return int(h[:8], 16) % 100


def enabled(
    name: str,
    *,
    default: bool = False,
    identity: str = "",
    repo=None,
) -> bool:
    """Return True if the named feature flag is enabled.

    Parameters:
        name: flag name (case-insensitive for env lookups)
        default: fallback if no env or DB config exists
        identity: string used for percentage rollouts (e.g. str(subscriber_id))
        repo: optional Repository instance; if provided, check the DB
              feature_flags table. Pass None to skip DB lookup.
    """
    # 1. Env override — strongest signal, no DB call required
    env = _env_value(name)
    if env is not None:
        return env

    # 2. DB lookup — optional, skip if no repo provided
    if repo is not None:
        try:
            row = repo.get_feature_flag(name)
        except Exception:
            logger.debug("feature_flags lookup failed for %s", name, exc_info=True)
            row = None
        if row:
            if not row.get("is_active"):
                return False
            pct = int(row.get("rollout_percent", 100) or 0)
            if pct >= 100:
                return True
            if pct <= 0:
                return False
            if not identity:
                # No identity → deterministic global decision based on the
                # flag name alone, so 50% rollout still gives the same answer
                # for every call until pct changes.
                identity = "__global__"
            return _rollout_bucket(identity, name) < pct

    # 3. Default
    return default
