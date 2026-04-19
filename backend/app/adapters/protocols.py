"""Protocol interfaces for external services. Service code depends only on these."""
from __future__ import annotations

from typing import Any, Protocol

from decimal import Decimal

from app.domain.binance import Kline, Ticker24h
from app.domain.markets import GammaEvent, GammaMarket
from app.domain.sentiment import FearGreedPoint, NewsItem
from app.domain.trades import Order, Position, TxReceipt


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


class OpenAIClient(Protocol):
    """Returns ``{"content": <json dict>, "tokens_used": int, "latency_ms": int}``."""
    async def predict(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, Any],
        seed: int,
        model: str,
    ) -> dict[str, Any]: ...


class PolymarketCLOBClient(Protocol):
    async def place_order(
        self, *, token_id: str, side: str, price: Decimal, size: Decimal,
    ) -> Order: ...

    async def get_order(self, order_id: str) -> Order: ...

    async def cancel_order(self, order_id: str) -> bool: ...

    async def get_positions(self) -> list[Position]: ...

    async def get_current_price(self, token_id: str) -> Decimal: ...


class VaultClient(Protocol):
    async def total_assets(self) -> Decimal: ...

    async def share_price(self) -> Decimal: ...

    async def available_balance(self) -> Decimal: ...

    async def withdraw_to_strategy(self, amount: Decimal) -> TxReceipt: ...

    async def deposit_from_strategy(self, amount: Decimal) -> TxReceipt: ...
