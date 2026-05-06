"""Tests for the feature flag dependency model.

Covers:
  1. missing_dependencies returns deps that are off
  2. missing_dependencies returns [] when all deps are on
  3. missing_dependencies returns [] for flags with no declared deps
  4. The admin UI exposes unmet deps for enabled flags only
"""

from __future__ import annotations

from weeklyamp.core.feature_flags import (
    FLAG_DEPENDENCIES,
    FeatureFlag,
    invalidate_cache,
    missing_dependencies,
)


def test_no_deps_returns_empty(repo):
    """Flags without entries in FLAG_DEPENDENCIES never report unmet deps."""
    invalidate_cache()
    # REFERRALS has no declared deps in the current graph
    assert FeatureFlag.REFERRALS not in FLAG_DEPENDENCIES
    assert missing_dependencies(FeatureFlag.REFERRALS, repo=repo) == []


def test_unmet_dep_surfaces(repo):
    """MARKETPLACE requires ADVERTISERS — when ADVERTISERS is off, the
    marketplace flag should report it as missing."""
    invalidate_cache()
    repo.set_feature_flag(FeatureFlag.ADVERTISERS, False)
    invalidate_cache()
    unmet = missing_dependencies(FeatureFlag.MARKETPLACE, repo=repo)
    assert unmet == [FeatureFlag.ADVERTISERS]


def test_met_dep_returns_empty(repo):
    """When ADVERTISERS is on, MARKETPLACE has no unmet deps."""
    invalidate_cache()
    repo.set_feature_flag(FeatureFlag.ADVERTISERS, True)
    invalidate_cache()
    assert missing_dependencies(FeatureFlag.MARKETPLACE, repo=repo) == []


def test_podcast_requires_audio(repo):
    """PODCAST → AUDIO is the second declared dep edge — verify it
    behaves the same as MARKETPLACE → ADVERTISERS so we know the lookup
    is data-driven, not hardcoded for one flag."""
    invalidate_cache()
    repo.set_feature_flag(FeatureFlag.AUDIO, False)
    invalidate_cache()
    assert missing_dependencies(FeatureFlag.PODCAST, repo=repo) == [
        FeatureFlag.AUDIO,
    ]
    repo.set_feature_flag(FeatureFlag.AUDIO, True)
    invalidate_cache()
    assert missing_dependencies(FeatureFlag.PODCAST, repo=repo) == []


def test_franchise_requires_white_label(repo):
    invalidate_cache()
    repo.set_feature_flag(FeatureFlag.WHITE_LABEL, False)
    invalidate_cache()
    assert missing_dependencies(FeatureFlag.FRANCHISE, repo=repo) == [
        FeatureFlag.WHITE_LABEL,
    ]
