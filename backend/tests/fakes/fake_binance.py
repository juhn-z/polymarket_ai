"""In-memory BinanceClient fake."""
from __future__ import annotations

from collections.abc import Mapping

from app.domain.binance import Kline, Ticker24h


class FakeBinanceClient:
    def __init__(
        self,
        klines: Mapping[tuple[str, str], list[Kline]] | None = None,
        tickers: Mapping[str, Ticker24h] | None = None,
    ) -> None:
        self._klines = dict(klines) if klines else {}
        self._tickers = dict(tickers) if tickers else {}
        self.kline_calls: list[tuple[str, str, int]] = []
        self.ticker_calls: list[str] = []

    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[Kline]:
        self.kline_calls.append((symbol, interval, limit))
        bucket = self._klines.get((symbol, interval), [])
        return list(bucket[-limit:])  # behave like Binance: tail

    async def get_24h_ticker(self, symbol: str) -> Ticker24h:
        self.ticker_calls.append(symbol)
        if symbol not in self._tickers:
            raise LookupError(f"No fake ticker configured for {symbol}")
        return self._tickers[symbol]
