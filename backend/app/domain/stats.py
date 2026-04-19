"""Domain types for system statistics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class VaultSnapshot:
    total_assets: Decimal
    share_price: Decimal
    tvl: Decimal
    depositor_count: int
    deployed_amount: Decimal
    snapshot_at: datetime
    id: int | None = None


@dataclass(frozen=True, slots=True)
class OverviewStats:
    tvl: Decimal
    share_price: Decimal
    total_pnl: Decimal
    total_trades: int
    win_rate: Decimal       # 0..1
    active_positions: int


@dataclass(frozen=True, slots=True)
class DailyPnL:
    day: date
    pnl: Decimal
    trade_count: int


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    rank: int
    wallet: str
    deposited: Decimal
    current_value: Decimal
    profit: Decimal
    profit_pct: Decimal
