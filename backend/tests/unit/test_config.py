"""Settings tests — the env-driven config surface deployments rely on.

The OpenAI adapter is OpenAI-compatible, so an OpenAI-compatible proxy
(e.g. AIHubMix) can be used by overriding only the base URL + model.
"""
from __future__ import annotations

import pytest

from app.config import Settings


def test_openai_base_url_defaults_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.openai_base_url == "https://api.openai.com/v1"


def test_openai_base_url_overridable_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://aihubmix.com/v1")
    settings = Settings(_env_file=None)
    assert settings.openai_base_url == "https://aihubmix.com/v1"
