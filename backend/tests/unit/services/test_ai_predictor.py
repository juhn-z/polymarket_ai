"""Unit tests for AIPredictor."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.domain.markets import Market
from app.domain.predictions import Prediction, PredictionDirection, PredictionRecommendation
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import MarketDataBundle
from tests.fakes.fake_openai import FakeOpenAIClient
from tests.fakes.fake_prediction_repository import FakePredictionRepository


def _market(*, yes_price: str = "0.55") -> Market:
    return Market(
        id=42,
        polymarket_condition_id="0xabc",
        polymarket_token_id="yes-token",
        event_slug="bitcoin-above",
        question="Bitcoin above 66000 on April 7?",
        price_threshold=66000,
        scan_date=date(2026, 4, 5),
        target_date=date(2026, 4, 7),
        current_yes_price=Decimal(yes_price),
        current_no_price=Decimal("1") - Decimal(yes_price),
        selected_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
    )


def _bundle() -> MarketDataBundle:
    return MarketDataBundle(
        timestamp=datetime(2026, 4, 5, 2, 0, tzinfo=timezone.utc),
        btc_current_price=Decimal("63500"),
        target_price=66000,
        target_datetime=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        high_24h=Decimal("64000"),
        low_24h=Decimal("63000"),
        volume_24h=Decimal("12345"),
        price_change_24h=Decimal("-1.25"),
        rsi_14=Decimal("38"),
        macd=None,
        bollinger=None,
        ema=None,
        atr=Decimal("850"),
        fear_greed_index=38,
        fear_greed_label="Fear",
        fear_greed_trend_7d=[40, 39, 38, 37, 38, 39, 38],
        news_headlines=[{"title": "ETF outflows", "source": "CoinDesk"}],
    )


def _canned_response() -> dict[str, Any]:
    return {
        "predicted_probability": 0.25,
        "confidence": 0.78,
        "direction": "bearish",
        "key_factors": [
            "BTC trading 3.8% BELOW threshold with only 36h",
            "ATR-implied move suggests <15% chance of crossing",
        ],
        "risk_factors": [
            "Potential short squeeze if funding flips negative",
            "FOMC dovish surprise possible",
        ],
        "technical_analysis": "RSI 38 oversold-but-not-extreme, MACD bearish crossover.",
        "sentiment_analysis": "F&G at 38 (Fear) trending down.",
        "news_impact": "Two consecutive days of ETF outflows.",
        "onchain_analysis": "Exchange inflows of $240M indicate distribution.",
        "reasoning": "BTC is currently $63,500, threshold is $66,000. With 36 hours to resolution and ATR=$850, the implied move is roughly $1,470; >2.5σ move required. Technical, on-chain, and sentiment signals all point bearish. My estimate is 25%, giving an edge of 30% in favor of No.",
        "recommended_action": "buy_no",
    }


class TestAIPredictor:
    async def test_predict_returns_prediction_with_canned_fields(self) -> None:
        openai = FakeOpenAIClient(response=_canned_response())
        repo = FakePredictionRepository()
        predictor = AIPredictor(openai=openai, repo=repo)

        prediction = await predictor.predict(_market(), _bundle())

        assert isinstance(prediction, Prediction)
        assert prediction.market_id == 42
        assert prediction.predicted_probability == Decimal("0.25")
        assert prediction.confidence == Decimal("0.78")
        assert prediction.direction == "bearish"
        assert prediction.recommended_action == "buy_no"
        assert len(prediction.key_factors) == 2

    async def test_predict_computes_edge_from_market_price(self) -> None:
        openai = FakeOpenAIClient(response=_canned_response())
        repo = FakePredictionRepository()
        predictor = AIPredictor(openai=openai, repo=repo)

        prediction = await predictor.predict(_market(yes_price="0.55"), _bundle())

        # edge = predicted_probability - market_yes_price = 0.25 - 0.55 = -0.30
        assert prediction.market_probability == Decimal("0.55")
        assert prediction.edge == Decimal("-0.30")

    async def test_predict_persists_via_repository(self) -> None:
        openai = FakeOpenAIClient(response=_canned_response())
        repo = FakePredictionRepository()
        predictor = AIPredictor(openai=openai, repo=repo)

        prediction = await predictor.predict(_market(), _bundle())

        assert prediction.id is not None
        assert await repo.get_by_id(prediction.id) is not None

    async def test_predict_sends_bundle_content_to_openai(self) -> None:
        openai = FakeOpenAIClient(response=_canned_response())
        repo = FakePredictionRepository()
        predictor = AIPredictor(openai=openai, repo=repo)

        await predictor.predict(_market(), _bundle())

        assert len(openai.calls) == 1
        call = openai.calls[0]
        # User prompt must contain key numerical facts from the bundle
        assert "66000" in call["user"]        # threshold
        assert "63500" in call["user"]        # current BTC price
        assert "38" in call["user"]            # RSI
        # System prompt should contain the 25% edge rule
        assert "0.25" in call["system"] or "25" in call["system"]

    async def test_predict_raises_on_schema_violation(self) -> None:
        """If the LLM returns something that can't be mapped, we refuse to persist."""
        bad_response = {"predicted_probability": 1.5, "confidence": 0.8}  # prob > 1, missing fields
        openai = FakeOpenAIClient(response=bad_response)
        repo = FakePredictionRepository()
        predictor = AIPredictor(openai=openai, repo=repo)

        with pytest.raises(ValueError):
            await predictor.predict(_market(), _bundle())

        assert await repo.list_all() == []  # nothing persisted on failure

    async def test_predict_stores_snapshot_and_raw_response(self) -> None:
        openai = FakeOpenAIClient(response=_canned_response())
        repo = FakePredictionRepository()
        predictor = AIPredictor(openai=openai, repo=repo)

        prediction = await predictor.predict(_market(), _bundle())

        assert prediction.raw_response == _canned_response()
        assert "btc_current_price" in prediction.data_snapshot
        assert prediction.data_snapshot["btc_current_price"] == "63500"
