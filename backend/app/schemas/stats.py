"""Pydantic schemas for /api/v1/stats + /api/v1/system."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OverviewResponse(BaseModel):
    tvl: Decimal
    share_price: Decimal
    total_pnl: Decimal
    total_trades: int
    win_rate: Decimal
    active_positions: int


class DailyPnLResponse(BaseModel):
    day: date
    pnl: Decimal
    trade_count: int


class VaultSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_assets: Decimal
    share_price: Decimal
    tvl: Decimal
    depositor_count: int
    deployed_amount: Decimal
    snapshot_at: datetime


class LeaderboardEntryResponse(BaseModel):
    rank: int
    wallet: str
    deposited: Decimal
    current_value: Decimal
    profit: Decimal
    profit_pct: Decimal


class SystemStatusResponse(BaseModel):
    paused: bool
    scheduler_running: bool
    monitor_running: bool
