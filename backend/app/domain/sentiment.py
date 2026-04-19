"""Domain types for market sentiment data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class FearGreedPoint:
    value: int                # 0-100
    label: str                # "Extreme Fear" .. "Extreme Greed"
    at: date


@dataclass(frozen=True, slots=True)
class NewsItem:
    id: int
    title: str
    source: str
    url: str
    published_at: datetime
