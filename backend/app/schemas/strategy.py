"""Pydantic response schemas for /api/v1/strategies."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.strategies import Strategy


class StrategyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_id: int
    market_id: int
    action: Literal["buy_yes", "buy_no", "skip"]
    side: Literal["yes", "no"] | None
    position_size: Decimal
    entry_price: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    kelly_fraction: Decimal
    edge: Decimal
    skip_reason: str
    status: Literal["skipped", "pending", "executing", "active", "closed", "failed"]
    created_at: datetime
    executed_at: datetime | None

    @classmethod
    def from_domain(cls, strategy: Strategy) -> "StrategyResponse":
        if strategy.id is None:
            raise ValueError("Cannot serialize unsaved Strategy")
        return cls(
            id=strategy.id,
            prediction_id=strategy.prediction_id,
            market_id=strategy.market_id,
            action=strategy.action,
            side=strategy.side,
            position_size=strategy.position_size,
            entry_price=strategy.entry_price,
            take_profit=strategy.take_profit,
            stop_loss=strategy.stop_loss,
            kelly_fraction=strategy.kelly_fraction,
            edge=strategy.edge,
            skip_reason=strategy.skip_reason,
            status=strategy.status,
            created_at=strategy.created_at,
            executed_at=strategy.executed_at,
        )
