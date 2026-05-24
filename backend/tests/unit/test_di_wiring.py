"""DI wiring tests — providers must thread settings into services.

These guard the config→service wiring that lets a deployment switch the
LLM model (e.g. gpt-5.5) purely via env, without code changes.
"""
from __future__ import annotations

from app.api.deps import get_ai_predictor
from app.config import Settings
from tests.fakes.fake_openai import FakeOpenAIClient


def test_get_ai_predictor_uses_configured_model() -> None:
    fake_openai = FakeOpenAIClient()
    settings = Settings(_env_file=None, openai_model="gpt-5.5")

    predictor = get_ai_predictor(openai=fake_openai, repo=object(), settings=settings)

    assert predictor._model == "gpt-5.5"
