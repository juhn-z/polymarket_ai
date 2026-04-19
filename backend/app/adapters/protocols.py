"""Protocol interfaces for external services. Service code depends only on these."""
from __future__ import annotations

from typing import Protocol

from app.domain.binance import Kline, Ticker24h
from app.domain.markets import GammaEvent, GammaMarket
from app.domain.sentiment import FearGreedPoint, NewsItem


class PolymarketGammaClient(Protocol):
    async def search_events(self, tag: str) -> list[GammaEvent]: ...

    async def get_event_markets(self, event_id: str) -> list[GammaMarket]: ...


class BinanceClient(Protocol):
    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[Kline]: ...

    async def get_24h_ticker(self, symbol: str) -> Ticker24h: ...


class FearGreedClient(Protocol):
    async def get_index(self, days: int = 7) -> list[FearGreedPoint]: ...


class NewsClient(Protocol):
    async def get_btc_news(self, limit: int = 10) -> list[NewsItem]: ...
