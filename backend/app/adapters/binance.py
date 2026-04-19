"""HTTP adapter for the Binance public API.

Only endpoints we use:
  - GET /api/v3/klines            — OHLCV candles
  - GET /api/v3/ticker/24hr       — 24h rolling ticker
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.domain.binance import Kline, Ticker24h

_DEFAULT_TIMEOUT_SECONDS = 15.0


class BinanceHttpClient:
    def __init__(
        self,
        base_url: str = "https://api.binance.com",
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[Kline]:
        response = await self._client.get(
            f"{self._base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        response.raise_for_status()
        return [_parse_kline(row) for row in response.json()]

    async def get_24h_ticker(self, symbol: str) -> Ticker24h:
        response = await self._client.get(
            f"{self._base_url}/api/v3/ticker/24hr",
            params={"symbol": symbol},
        )
        response.raise_for_status()
        return _parse_ticker(response.json())


def _parse_kline(row: list) -> Kline:
    return Kline(
        open_time=_ms_to_utc(row[0]),
        open=Decimal(row[1]),
        high=Decimal(row[2]),
        low=Decimal(row[3]),
        close=Decimal(row[4]),
        volume=Decimal(row[5]),
        close_time=_ms_to_utc(row[6]),
    )


def _parse_ticker(payload: dict) -> Ticker24h:
    return Ticker24h(
        symbol=payload["symbol"],
        last_price=Decimal(payload["lastPrice"]),
        high_price=Decimal(payload["highPrice"]),
        low_price=Decimal(payload["lowPrice"]),
        volume=Decimal(payload["volume"]),
        price_change=Decimal(payload["priceChange"]),
        price_change_percent=Decimal(payload["priceChangePercent"]),
    )


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
