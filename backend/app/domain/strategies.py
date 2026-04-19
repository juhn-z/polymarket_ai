"""Domain types for trading strategies."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

StrategyAction = Literal["buy_yes", "buy_no", "skip"]
StrategySide = Literal["yes", "no"]
StrategyStatus = Literal[
    "skipped",     # hard gate failed — never traded
    "pending",     # generated but not yet executed
    "executing",   # Executor is placing orders
    "active",      # position open on Polymarket
    "closed",      # position closed (TP, SL, or resolution)
    "failed",      # execution error
]


@dataclass
class Strategy:
    prediction_id: int
    market_id: int
    action: StrategyAction
    side: StrategySide | None              # None when action=skip
    position_size: Decimal                  # USDC (0 for skip)
    entry_price: Decimal                    # 0 for skip
    take_profit: Decimal                    # 0 for skip
    stop_loss: Decimal                      # 0 for skip
    kelly_fraction: Decimal                 # 0 for skip
    edge: Decimal                           # signed edge used to decide
    skip_reason: str                        # empty for non-skip
    status: StrategyStatus = "pending"
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: datetime | None = None


__all__ = [
    "Strategy",
    "StrategyAction",
    "StrategySide",
    "StrategyStatus",
]
