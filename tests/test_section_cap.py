"""Tests for the per-issue section cap and the review-model split.

Two cost controls land together here:

  1. ``get_draftable_section_slugs`` bounds how many sections one drafting
     run generates. Before the cap, every run drafted the entire library
     (74 active sections in production), which is one API call per section
     plus one editor-review call per resulting draft.
  2. ``resolve_review_model`` routes the cheap, high-volume scoring passes
     to a smaller model than the one writing reader-facing prose.

The cap has to respect editorial structure, not just truncate: core
sections are the spine of every issue and must survive the cut.

The test database ships with the default section library already seeded,
so these assert relative properties rather than absolute counts.
"""

from __future__ import annotations

import pytest

from weeklyamp.content.generator import resolve_review_model
from weeklyamp.content.sections import (
    get_draftable_section_slugs,
    get_section_slugs,
)
from weeklyamp.core.models import AIConfig, AppConfig


@pytest.fixture()
def library(repo):
    """The seeded section library, with its core/rotating split measured."""
    all_slugs = get_section_slugs(repo)
    core = [s["slug"] for s in repo.get_sections_by_type("core") if s["slug"] in all_slugs]
    assert len(all_slugs) > 20, "seeded library should be larger than one issue"
    assert core, "seeded library should define core sections"
    return {"repo": repo, "all": all_slugs, "core": core}


def _config(cap: int) -> AppConfig:
    return AppConfig(ai=AIConfig(max_sections_per_issue=cap))


def test_uncapped_returns_whole_library(library):
    """cap=0 preserves the old behaviour — draft everything."""
    slugs = get_draftable_section_slugs(library["repo"], _config(0))
    assert slugs == library["all"]


def test_no_config_returns_whole_library(library):
    """A caller that passes no config is not silently capped."""
    assert get_draftable_section_slugs(library["repo"], None) == library["all"]


def test_cap_limits_the_run(library):
    slugs = get_draftable_section_slugs(library["repo"], _config(15))
    assert len(slugs) == 15
    assert len(slugs) < len(library["all"])


def test_every_core_section_survives_the_cap(library):
    """Core sections are the issue's spine — the cap fills around them."""
    cap = len(library["core"]) + 5
    slugs = get_draftable_section_slugs(library["repo"], _config(cap))
    for slug in library["core"]:
        assert slug in slugs, f"core section {slug} was dropped by the cap"


def test_remaining_slots_are_filled(library):
    """The cap is a ceiling, not a target it undershoots."""
    cap = len(library["core"]) + 5
    slugs = get_draftable_section_slugs(library["repo"], _config(cap))
    assert len(slugs) == cap


def test_cap_smaller_than_core_count_still_holds(library):
    """A cap below the core count truncates rather than overrunning budget."""
    cap = max(1, len(library["core"]) - 1)
    slugs = get_draftable_section_slugs(library["repo"], _config(cap))
    assert len(slugs) == cap
    assert set(slugs).issubset(set(library["core"]))


def test_cap_larger_than_library_is_harmless(library):
    slugs = get_draftable_section_slugs(library["repo"], _config(10_000))
    assert slugs == library["all"]


def test_output_follows_sort_order(library):
    """Running order is preserved, so the cap doesn't scramble the issue."""
    slugs = get_draftable_section_slugs(library["repo"], _config(15))
    positions = [library["all"].index(s) for s in slugs]
    assert positions == sorted(positions)


def test_no_duplicate_sections(library):
    """A section in both core and rotation must not be drafted twice."""
    slugs = get_draftable_section_slugs(library["repo"], _config(15))
    assert len(slugs) == len(set(slugs))


def test_every_returned_slug_is_a_real_active_section(library):
    slugs = get_draftable_section_slugs(library["repo"], _config(15))
    assert set(slugs).issubset(set(library["all"]))


# --- review model split ---


def test_review_model_used_when_set():
    cfg = AppConfig(ai=AIConfig(model="writer-model", review_model="cheap-model"))
    assert resolve_review_model(cfg) == "cheap-model"


def test_review_model_falls_back_to_main_model():
    """A config predating the split keeps working on a single model."""
    cfg = AppConfig(ai=AIConfig(model="writer-model", review_model=""))
    assert resolve_review_model(cfg) == "writer-model"


def test_review_model_ignores_whitespace_only_value():
    cfg = AppConfig(ai=AIConfig(model="writer-model", review_model="   "))
    assert resolve_review_model(cfg) == "writer-model"


def test_shipped_config_splits_the_tiers():
    """The defaults actually enable the split — not just support it."""
    cfg = AppConfig()
    assert resolve_review_model(cfg) != cfg.ai.model
    assert cfg.ai.max_sections_per_issue > 0


# --- the agent path must honour the cap too ---------------------------


def test_editor_assign_sections_respects_the_cap(repo, library):
    """The agent path generates the telemetry the cost dashboard reads, so
    a cap it ignores would silently undo the saving twice over — one write
    call and one review call per extra section."""
    from weeklyamp.agents.editor import EditorInChiefAgent

    cap = 6
    issue_id = repo.create_issue(1, title="Cap test")
    repo.create_agent("writer", "Test Writer")
    agent = EditorInChiefAgent(repo, _config(cap))
    task_id = agent.assign_task("assign_sections", issue_id=issue_id)
    result = agent.execute(task_id)

    assert result.get("assigned") == cap, result
    assigned = {t["section"] for t in result["tasks"]}
    assert len(assigned) == cap
    assert assigned.issubset(set(library["all"]))
    for slug in library["core"][:cap]:
        assert slug in assigned


# --- sampling params must not be sent to models that reject them -------


@pytest.mark.parametrize("model", [
    "claude-sonnet-5", "claude-opus-5", "claude-opus-4-7",
    "claude-opus-4-8", "claude-fable-5", "claude-mythos-5",
])
def test_current_generation_rejects_sampling_params(model):
    """Sending temperature to these returns a 400 the generator swallows,
    which surfaces as an empty draft rather than an error."""
    from weeklyamp.content.generator import supports_sampling_params
    assert supports_sampling_params(model) is False


@pytest.mark.parametrize("model", [
    "claude-sonnet-4-5-20250929", "claude-haiku-4-5",
    "claude-opus-4-6", "claude-sonnet-4-6", "gpt-4o", "some-proxy-model",
])
def test_older_and_unknown_models_still_get_sampling_params(model):
    """Unrecognised names keep the pre-4.7 behaviour rather than silently
    dropping a parameter the caller set on purpose."""
    from weeklyamp.content.generator import supports_sampling_params
    assert supports_sampling_params(model) is True


def test_temperature_omitted_for_rejecting_model(monkeypatch):
    """The request body must not carry temperature for a 5-series model."""
    from weeklyamp.content import generator

    captured = {}

    class _Msg:
        content = [type("B", (), {"text": "ok"})()]
        usage = type("U", (), {"input_tokens": 10, "output_tokens": 5})()

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Msg()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(generator, "anthropic", type("M", (), {"Anthropic": lambda: _Client()}), raising=False)
    monkeypatch.setitem(__import__("sys").modules, "anthropic",
                        type("M", (), {"Anthropic": staticmethod(lambda: _Client())}))

    cfg = AppConfig(ai=AIConfig(model="claude-sonnet-5", temperature=0.7))
    content, model, tokens = generator.generate_draft_with_usage("hi", cfg)

    assert content == "ok"
    assert model == "claude-sonnet-5"
    assert tokens == 15
    assert "temperature" not in captured, captured


def test_temperature_sent_for_accepting_model(monkeypatch):
    from weeklyamp.content import generator

    captured = {}

    class _Msg:
        content = [type("B", (), {"text": "ok"})()]
        usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Msg()

    class _Client:
        messages = _Messages()

    monkeypatch.setitem(__import__("sys").modules, "anthropic",
                        type("M", (), {"Anthropic": staticmethod(lambda: _Client())}))

    cfg = AppConfig(ai=AIConfig(model="claude-haiku-4-5", temperature=0.3))
    generator.generate_draft_with_usage("hi", cfg)
    assert captured.get("temperature") == 0.3
