"""Live smoke tests against the real Binance API.

Run: ``pytest -m live tests/live/test_binance_schema.py``
"""
from __future__ import annotations

import pytest

from app.adapters.binance import BinanceHttpClient

pytestmark = pytest.mark.live


async def test_klines_shape_matches_adapter() -> None:
    client = BinanceHttpClient()
    try:
        klines = await client.get_klines("BTCUSDT", "1h", limit=3)
    finally:
        await client.aclose()

    assert len(klines) == 3
    for k in klines:
        assert k.open > 0
        assert k.high >= k.open
        assert k.low <= k.open
        assert k.volume >= 0


async def test_24h_ticker_shape_matches_adapter() -> None:
    client = BinanceHttpClient()
    try:
        ticker = await client.get_24h_ticker("BTCUSDT")
    finally:
        await client.aclose()

    assert ticker.symbol == "BTCUSDT"
    assert ticker.last_price > 0
    assert ticker.high_price >= ticker.low_price
