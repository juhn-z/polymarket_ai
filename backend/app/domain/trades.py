"""Domain types for Polymarket trades + vault + on-chain receipts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

TradeSide = Literal["yes", "no"]
TradeAction = Literal["buy", "sell"]
TradeStatus = Literal["pending", "filled", "partial", "cancelled", "failed"]
CloseReason = Literal["take_profit", "stop_loss", "pre_resolution", "manual"]


@dataclass(frozen=True, slots=True)
class Order:
    """Snapshot of a Polymarket CLOB order."""
    order_id: str
    token_id: str
    side: TradeAction
    price: Decimal
    size: Decimal
    filled_size: Decimal
    status: str  # pending / filled / partial / cancelled
    fee: Decimal


@dataclass(frozen=True, slots=True)
class Position:
    """A CLOB position snapshot."""
    token_id: str
    balance: Decimal
    avg_price: Decimal


@dataclass(frozen=True, slots=True)
class TxReceipt:
    """EVM transaction receipt summary."""
    tx_hash: str
    block_number: int
    status: int  # 1 = success, 0 = revert


@dataclass
class Trade:
    strategy_id: int
    market_id: int
    polymarket_order_id: str
    side: TradeSide
    action: TradeAction            # buy when opening, sell when closing
    amount: Decimal                # USDC amount (for buy) or proceeds (for sell)
    price: Decimal                 # execution price
    shares: Decimal                # token shares (positive for buy, same for sell)
    status: TradeStatus
    fee: Decimal = Decimal("0")
    pnl: Decimal | None = None
    close_reason: CloseReason | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: datetime | None = None
    closed_at: datetime | None = None
    id: int | None = None


__all__ = [
    "Trade",
    "TradeSide",
    "TradeAction",
    "TradeStatus",
    "Order",
    "Position",
    "TxReceipt",
    "CloseReason",
]
