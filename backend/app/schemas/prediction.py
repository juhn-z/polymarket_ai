"""Pydantic response schemas for /api/v1/predictions."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.domain.predictions import Prediction


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: int
    predicted_probability: Decimal
    confidence: Decimal
    direction: Literal["bullish", "bearish", "neutral"]
    key_factors: list[str]
    risk_factors: list[str]
    technical_analysis: str
    sentiment_analysis: str
    news_impact: str
    onchain_analysis: str
    reasoning: str
    recommended_action: Literal["buy_yes", "buy_no", "skip"]
    market_probability: Decimal
    edge: Decimal
    model_version: str
    prompt_version: str
    seed: int
    tokens_used: int
    latency_ms: int
    created_at: datetime

    @classmethod
    def from_domain(cls, prediction: Prediction) -> "PredictionResponse":
        if prediction.id is None:
            raise ValueError("Cannot serialize unsaved Prediction")
        return cls(
            id=prediction.id,
            market_id=prediction.market_id,
            predicted_probability=prediction.predicted_probability,
            confidence=prediction.confidence,
            direction=prediction.direction,
            key_factors=prediction.key_factors,
            risk_factors=prediction.risk_factors,
            technical_analysis=prediction.technical_analysis,
            sentiment_analysis=prediction.sentiment_analysis,
            news_impact=prediction.news_impact,
            onchain_analysis=prediction.onchain_analysis,
            reasoning=prediction.reasoning,
            recommended_action=prediction.recommended_action,
            market_probability=prediction.market_probability,
            edge=prediction.edge,
            model_version=prediction.model_version,
            prompt_version=prediction.prompt_version,
            seed=prediction.seed,
            tokens_used=prediction.tokens_used,
            latency_ms=prediction.latency_ms,
            created_at=prediction.created_at,
        )


class PredictionDetailResponse(PredictionResponse):
    """Detail view adds raw_request/raw_response/data_snapshot."""
    raw_request: dict[str, Any]
    raw_response: dict[str, Any]
    data_snapshot: dict[str, Any]

    @classmethod
    def from_domain(cls, prediction: Prediction) -> "PredictionDetailResponse":
        base = PredictionResponse.from_domain(prediction).model_dump()
        return cls(
            **base,
            raw_request=prediction.raw_request,
            raw_response=prediction.raw_response,
            data_snapshot=prediction.data_snapshot,
        )
