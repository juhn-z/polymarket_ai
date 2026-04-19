"""Domain types for Binance market data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Kline:
    """OHLCV candlestick for a single interval."""
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime


@dataclass(frozen=True, slots=True)
class Ticker24h:
    """24h rolling ticker snapshot."""
    symbol: str
    last_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal
    price_change: Decimal
    price_change_percent: Decimal
