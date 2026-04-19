"""Domain types for AI predictions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

PredictionDirection = Literal["bullish", "bearish", "neutral"]
PredictionRecommendation = Literal["buy_yes", "buy_no", "skip"]


@dataclass
class Prediction:
    """A single AI-generated probability estimate for one Market."""
    market_id: int
    predicted_probability: Decimal   # 0.01..0.99
    confidence: Decimal              # 0..1
    direction: PredictionDirection
    key_factors: list[str]
    risk_factors: list[str]
    technical_analysis: str
    sentiment_analysis: str
    news_impact: str
    onchain_analysis: str
    reasoning: str
    recommended_action: PredictionRecommendation
    market_probability: Decimal      # Polymarket yes price at prediction time
    edge: Decimal                    # predicted_probability - market_probability
    model_version: str
    prompt_version: str
    seed: int
    raw_request: dict[str, Any]
    raw_response: dict[str, Any]
    data_snapshot: dict[str, Any]
    tokens_used: int = 0
    latency_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: int | None = None


__all__ = [
    "Prediction",
    "PredictionDirection",
    "PredictionRecommendation",
]
