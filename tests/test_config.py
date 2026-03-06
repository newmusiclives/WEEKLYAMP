"""Tests for configuration loading and environment variable overrides."""

from __future__ import annotations

import os

import pytest

from weeklyamp.core.config import load_config
from weeklyamp.core.models import AIProvider, AppConfig


def test_load_config_returns_valid_appconfig():
    config = load_config()
    assert isinstance(config, AppConfig)
    assert config.newsletter.name  # should have a default name
    assert config.ai.provider in (AIProvider.ANTHROPIC, AIProvider.OPENAI)
    assert config.ai.max_tokens > 0
    assert config.ai.temperature >= 0
    assert isinstance(config.db_path, str)


def test_load_config_has_default_db_path():
    config = load_config()
    assert "weeklyamp" in config.db_path or config.db_path


def test_load_config_has_schedule():
    config = load_config()
    assert config.schedule.frequency >= 1
    assert isinstance(config.schedule.send_days, list)


def test_load_config_has_submissions():
    config = load_config()
    assert isinstance(config.submissions.auto_acknowledge, bool)
    assert isinstance(config.submissions.require_email, bool)


# ---- Environment variable overrides ----

def test_env_override_ai_provider(monkeypatch):
    monkeypatch.setenv("WEEKLYAMP_AI_PROVIDER", "openai")
    config = load_config()
    assert config.ai.provider == AIProvider.OPENAI


def test_env_override_ai_model(monkeypatch):
    monkeypatch.setenv("WEEKLYAMP_AI_MODEL", "gpt-4o")
    config = load_config()
    assert config.ai.model == "gpt-4o"


def test_env_override_db_path(monkeypatch):
    monkeypatch.setenv("WEEKLYAMP_DB_PATH", "/tmp/custom.db")
    config = load_config()
    assert config.db_path == "/tmp/custom.db"


def test_env_override_submissions_api_key(monkeypatch):
    monkeypatch.setenv("TRUEFANS_SUBMISSIONS_API_KEY", "test-key-abc")
    config = load_config()
    assert config.submissions.api_key == "test-key-abc"


def test_env_override_email_config(monkeypatch):
    monkeypatch.setenv("WEEKLYAMP_EMAIL_ENABLED", "true")
    monkeypatch.setenv("WEEKLYAMP_SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("WEEKLYAMP_SMTP_PORT", "465")
    monkeypatch.setenv("WEEKLYAMP_EMAIL_FROM", "test@test.com")
    config = load_config()
    assert config.email.enabled is True
    assert config.email.smtp_host == "smtp.test.com"
    assert config.email.smtp_port == 465
    assert config.email.from_address == "test@test.com"
