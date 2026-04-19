"""Pydantic response schemas for /api/v1/trades."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.trades import Trade


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_id: int
    market_id: int
    polymarket_order_id: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    amount: Decimal
    price: Decimal
    shares: Decimal
    status: Literal["pending", "filled", "partial", "cancelled", "failed"]
    fee: Decimal
    pnl: Decimal | None
    close_reason: Literal["take_profit", "stop_loss", "pre_resolution", "manual"] | None
    created_at: datetime
    filled_at: datetime | None
    closed_at: datetime | None

    @classmethod
    def from_domain(cls, trade: Trade) -> "TradeResponse":
        if trade.id is None:
            raise ValueError("Cannot serialize unsaved Trade")
        return cls(
            id=trade.id,
            strategy_id=trade.strategy_id,
            market_id=trade.market_id,
            polymarket_order_id=trade.polymarket_order_id,
            side=trade.side,
            action=trade.action,
            amount=trade.amount,
            price=trade.price,
            shares=trade.shares,
            status=trade.status,
            fee=trade.fee,
            pnl=trade.pnl,
            close_reason=trade.close_reason,
            created_at=trade.created_at,
            filled_at=trade.filled_at,
            closed_at=trade.closed_at,
        )
