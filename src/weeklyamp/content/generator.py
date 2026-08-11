"""AI draft generation engine supporting Anthropic and OpenAI.

Two public entry points:

* :func:`generate_draft` returns ``(content, model)`` — kept for
  backward compatibility with the ~30 callers across agents/, guests/,
  i18n, etc. that unpack the 2-tuple.
* :func:`generate_draft_with_usage` returns
  ``(content, model, tokens_used)`` where ``tokens_used`` is the
  ``input_tokens + output_tokens`` count reported by the provider.
  Callers that want accurate cost telemetry (writer.log_output,
  cost-tracking dashboards) should use this path.
"""

from __future__ import annotations

import logging
from typing import Optional

from weeklyamp.core.models import AIProvider, AppConfig

logger = logging.getLogger(__name__)


# Model families that reject `temperature` / `top_p` / `top_k` outright.
# Sending a non-default sampling parameter to one of these returns
# 400 "`temperature` is deprecated for this model" — and because the
# call sites below swallow provider errors, that surfaces as an empty
# draft rather than a crash. Older families (Sonnet 4.5/4.6, Haiku 4.5,
# Opus 4.5/4.6) still accept sampling params.
_SAMPLING_REJECTED_PREFIXES: tuple[str, ...] = (
    "claude-opus-5",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
)


def supports_sampling_params(model: str) -> bool:
    """Whether *model* accepts ``temperature`` and friends.

    Conservative by prefix: an unrecognised model is assumed to accept
    them, which matches how every model behaved before the 4.7/5
    generation and keeps custom or proxied model names working.
    """
    name = (model or "").strip().lower()
    return not name.startswith(_SAMPLING_REJECTED_PREFIXES)


def resolve_review_model(config: AppConfig) -> str:
    """Return the model to use for scoring / short-critique passes.

    Falls back to the main model when ``review_model`` is unset, so a
    config that predates the split keeps working unchanged.
    """
    return (getattr(config.ai, "review_model", "") or "").strip() or config.ai.model


def generate_draft(
    prompt: str,
    config: AppConfig,
    max_tokens_override: Optional[int] = None,
    system_prompt: Optional[str] = None,
    model_override: Optional[str] = None,
) -> tuple[str, str]:
    """Generate a draft using the configured AI provider.

    Returns (content, model_used). For cost telemetry, prefer
    :func:`generate_draft_with_usage`.
    """
    content, model, _tokens = generate_draft_with_usage(
        prompt, config, max_tokens_override, system_prompt, model_override
    )
    return content, model


def generate_draft_with_usage(
    prompt: str,
    config: AppConfig,
    max_tokens_override: Optional[int] = None,
    system_prompt: Optional[str] = None,
    model_override: Optional[str] = None,
) -> tuple[str, str, int]:
    """Like :func:`generate_draft` but also returns actual tokens used.

    Returns (content, model_used, tokens_used). ``tokens_used`` is 0 if
    the provider call failed or the provider didn't report usage.

    ``model_override`` sends this one call to a different model than
    ``config.ai.model`` — used by the cheap high-volume passes. The
    returned model name is the one actually called, so cost telemetry
    attributes tokens to the right price tier.
    """
    if config.ai.provider == AIProvider.ANTHROPIC:
        return _generate_anthropic(
            prompt, config, max_tokens_override, system_prompt, model_override
        )
    elif config.ai.provider == AIProvider.OPENAI:
        return _generate_openai(
            prompt, config, max_tokens_override, system_prompt, model_override
        )
    else:
        raise ValueError(f"Unknown AI provider: {config.ai.provider}")


def _generate_anthropic(
    prompt: str, config: AppConfig, max_tokens_override: Optional[int] = None,
    system_prompt: Optional[str] = None, model_override: Optional[str] = None,
) -> tuple[str, str, int]:
    """Generate using the Anthropic API. Returns (content, model, tokens_used).

    ``tokens_used`` is input_tokens + output_tokens from ``message.usage``;
    this is what the cost tracking in project_cost_tracking memory is
    designed around. Returning 0 on failure keeps callers from division-
    by-zero errors when computing cost-per-edition.
    """
    import anthropic

    max_tokens = max_tokens_override or config.ai.max_tokens
    model = model_override or config.ai.model

    kwargs: dict = dict(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if supports_sampling_params(model):
        kwargs["temperature"] = config.ai.temperature
    if system_prompt:
        kwargs["system"] = system_prompt

    try:
        client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
        message = client.messages.create(**kwargs)
        content = message.content[0].text
        usage = getattr(message, "usage", None)
        tokens_used = 0
        if usage is not None:
            tokens_used = int(
                getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
            )
        return content, model, tokens_used
    except Exception:
        logger.exception("Anthropic API call failed")
        return "", model, 0


def _generate_openai(
    prompt: str, config: AppConfig, max_tokens_override: Optional[int] = None,
    system_prompt: Optional[str] = None, model_override: Optional[str] = None,
) -> tuple[str, str, int]:
    """Generate using the OpenAI API. Returns (content, model, tokens_used)."""
    import openai

    max_tokens = max_tokens_override or config.ai.max_tokens
    model = model_override or config.ai.model

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        client = openai.OpenAI()  # uses OPENAI_API_KEY env var
        openai_kwargs: dict = dict(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        if supports_sampling_params(model):
            openai_kwargs["temperature"] = config.ai.temperature
        response = client.chat.completions.create(**openai_kwargs)
        content = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        tokens_used = int(getattr(usage, "total_tokens", 0)) if usage else 0
        return content, model, tokens_used
    except Exception:
        logger.exception("OpenAI API call failed")
        return "", model, 0
