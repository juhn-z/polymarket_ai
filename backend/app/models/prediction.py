"""SQLAlchemy ORM for the predictions table."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PredictionORM(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)

    predicted_probability: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)

    key_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    risk_factors: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    technical_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    news_impact: Mapped[str] = mapped_column(Text, nullable=False)
    onchain_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(16), nullable=False)

    market_probability: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    edge: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)

    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    raw_request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    data_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
