"""Unit tests for BinanceHttpClient (real HTTP, mocked with respx)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
import respx

from app.adapters.binance import BinanceHttpClient


@pytest.fixture
def client() -> BinanceHttpClient:
    return BinanceHttpClient(base_url="https://api.binance.com")


@respx.mock
async def test_get_klines_parses_binance_array_response(client: BinanceHttpClient) -> None:
    # Binance returns klines as arrays of 12 elements:
    #   [openTime, open, high, low, close, volume, closeTime, quoteAssetVolume,
    #    numberOfTrades, takerBuyBaseVolume, takerBuyQuoteVolume, ignore]
    respx.get("https://api.binance.com/api/v3/klines").mock(
        return_value=httpx.Response(
            200,
            json=[
                [
                    1712361600000,  # openTime (2024-04-06 00:00 UTC)
                    "66500.00", "67200.00", "66100.00", "67000.00",
                    "1234.56", 1712365199999,
                    "82500000.00", 9876,
                    "600.00", "40000000.00", "0",
                ],
                [
                    1712365200000,  # openTime (2024-04-06 01:00 UTC)
                    "67000.00", "67500.00", "66900.00", "67300.00",
                    "987.65", 1712368799999,
                    "66000000.00", 5432,
                    "500.00", "33000000.00", "0",
                ],
            ],
        )
    )

    klines = await client.get_klines("BTCUSDT", "1h", limit=2)

    assert len(klines) == 2
    k0 = klines[0]
    assert k0.open_time == datetime(2024, 4, 6, 0, 0, tzinfo=timezone.utc)
    assert k0.open == Decimal("66500.00")
    assert k0.high == Decimal("67200.00")
    assert k0.low == Decimal("66100.00")
    assert k0.close == Decimal("67000.00")
    assert k0.volume == Decimal("1234.56")


@respx.mock
async def test_get_klines_sends_correct_query_params(client: BinanceHttpClient) -> None:
    route = respx.get("https://api.binance.com/api/v3/klines").mock(
        return_value=httpx.Response(200, json=[])
    )

    await client.get_klines("BTCUSDT", "1d", limit=30)

    assert route.called
    params = route.calls.last.request.url.params
    assert params["symbol"] == "BTCUSDT"
    assert params["interval"] == "1d"
    assert params["limit"] == "30"


@respx.mock
async def test_get_24h_ticker_parses_response(client: BinanceHttpClient) -> None:
    respx.get("https://api.binance.com/api/v3/ticker/24hr").mock(
        return_value=httpx.Response(
            200,
            json={
                "symbol": "BTCUSDT",
                "priceChange": "1500.00",
                "priceChangePercent": "2.25",
                "lastPrice": "68000.00",
                "highPrice": "68500.00",
                "lowPrice": "66200.00",
                "volume": "12345.67",
                "quoteVolume": "840000000.00",
                "openTime": 1712275200000,
                "closeTime": 1712361599999,
            },
        )
    )

    ticker = await client.get_24h_ticker("BTCUSDT")

    assert ticker.symbol == "BTCUSDT"
    assert ticker.last_price == Decimal("68000.00")
    assert ticker.high_price == Decimal("68500.00")
    assert ticker.low_price == Decimal("66200.00")
    assert ticker.volume == Decimal("12345.67")
    assert ticker.price_change_percent == Decimal("2.25")
