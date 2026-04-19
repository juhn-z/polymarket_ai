"""Pydantic schemas for the markets API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.markets import Market


class MarketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    polymarket_condition_id: str
    polymarket_token_id: str
    event_slug: str
    question: str
    price_threshold: int
    target_date: date
    current_yes_price: Decimal
    current_no_price: Decimal
    selected_at: datetime
    status: Literal["active", "resolved", "expired"]
    resolution: Literal["yes", "no"] | None

    @classmethod
    def from_domain(cls, market: Market) -> "MarketResponse":
        if market.id is None:
            raise ValueError("Cannot serialize unsaved Market (id is None)")
        return cls(
            id=market.id,
            polymarket_condition_id=market.polymarket_condition_id,
            polymarket_token_id=market.polymarket_token_id,
            event_slug=market.event_slug,
            question=market.question,
            price_threshold=market.price_threshold,
            target_date=market.target_date,
            current_yes_price=market.current_yes_price,
            current_no_price=market.current_no_price,
            selected_at=market.selected_at,
            status=market.status,
            resolution=market.resolution,
        )
