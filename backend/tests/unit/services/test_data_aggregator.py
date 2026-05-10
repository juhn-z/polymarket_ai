"""Unit tests for DataAggregator.collect_for."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.binance import Kline, Ticker24h
from app.domain.markets import Market
from app.domain.sentiment import FearGreedPoint, NewsItem
from app.services.data_aggregator import DataAggregator, MarketDataBundle
from tests.fakes.fake_binance import FakeBinanceClient
from tests.fakes.fake_sentiment import FakeFearGreedClient, FakeNewsClient

BTC_SYMBOL = "BTCUSDT"


def _market() -> Market:
    return Market(
        id=1,
        polymarket_condition_id="0xabc",
        polymarket_token_id="yes-token",
        event_slug="bitcoin-above-april-7",
        question="Bitcoin above 66000 on April 7?",
        price_threshold=66000,
        scan_date=date(2026, 4, 5),
        target_date=date(2026, 4, 7),
        current_yes_price=Decimal("0.50"),
        current_no_price=Decimal("0.50"),
        selected_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
    )


def _kline_series(count: int, symbol_close: float = 67000.0) -> list[Kline]:
    base = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
    return [
        Kline(
            open_time=base + timedelta(hours=i),
            close_time=base + timedelta(hours=i, minutes=59, seconds=59),
            open=Decimal(str(symbol_close + i)),
            high=Decimal(str(symbol_close + i + 50)),
            low=Decimal(str(symbol_close + i - 50)),
            close=Decimal(str(symbol_close + i + 1)),
            volume=Decimal("100"),
        )
        for i in range(count)
    ]


def _ticker() -> Ticker24h:
    return Ticker24h(
        symbol=BTC_SYMBOL,
        last_price=Decimal("68000"),
        high_price=Decimal("68500"),
        low_price=Decimal("66000"),
        volume=Decimal("12345"),
        price_change=Decimal("500"),
        price_change_percent=Decimal("0.74"),
    )


def _fng_points(n: int = 7) -> list[FearGreedPoint]:
    return [
        FearGreedPoint(value=50 + i, label="Neutral", at=date(2026, 4, 5) - timedelta(days=i))
        for i in range(n)
    ]


def _news(n: int = 3) -> list[NewsItem]:
    base = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
    return [
        NewsItem(
            id=i,
            title=f"News {i}",
            source="CoinDesk",
            url=f"https://example.com/{i}",
            published_at=base - timedelta(hours=i),
        )
        for i in range(n)
    ]


def _aggregator(
    klines_1h: list[Kline] | None = None,
    klines_1d: list[Kline] | None = None,
    ticker: Ticker24h | None = None,
    fng: list[FearGreedPoint] | None = None,
    news: list[NewsItem] | None = None,
) -> tuple[DataAggregator, FakeBinanceClient, FakeFearGreedClient, FakeNewsClient]:
    binance = FakeBinanceClient(
        klines={
            (BTC_SYMBOL, "1h"): klines_1h if klines_1h is not None else _kline_series(24 * 7),
            (BTC_SYMBOL, "1d"): klines_1d if klines_1d is not None else _kline_series(30),
        },
        tickers={BTC_SYMBOL: ticker if ticker else _ticker()},
    )
    fng_client = FakeFearGreedClient(points=fng if fng is not None else _fng_points())
    news_client = FakeNewsClient(items=news if news is not None else _news())
    agg = DataAggregator(binance=binance, fear_greed=fng_client, news=news_client)
    return agg, binance, fng_client, news_client


class TestDataAggregator:
    async def test_returns_market_data_bundle(self) -> None:
        agg, *_ = _aggregator()

        bundle = await agg.collect_for(_market())

        assert isinstance(bundle, MarketDataBundle)
        assert bundle.target_price == 66000
        assert bundle.target_datetime.date() == date(2026, 4, 7)

    async def test_fetches_1h_klines_for_last_7_days(self) -> None:
        agg, binance, _, _ = _aggregator()

        await agg.collect_for(_market())

        assert (BTC_SYMBOL, "1h", 24 * 7) in binance.kline_calls

    async def test_fetches_1d_klines_for_last_30_days(self) -> None:
        agg, binance, _, _ = _aggregator()

        await agg.collect_for(_market())

        assert (BTC_SYMBOL, "1d", 30) in binance.kline_calls

    async def test_populates_current_price_from_ticker(self) -> None:
        agg, *_ = _aggregator()

        bundle = await agg.collect_for(_market())

        assert bundle.btc_current_price == Decimal("68000")
        assert bundle.price_change_24h == Decimal("0.74")

    async def test_populates_fear_greed_from_adapter(self) -> None:
        agg, _, fng_client, _ = _aggregator(
            fng=[FearGreedPoint(value=72, label="Greed", at=date(2026, 4, 5))]
        )

        bundle = await agg.collect_for(_market())

        assert bundle.fear_greed_index == 72
        assert bundle.fear_greed_label == "Greed"
        assert fng_client.calls == [7]

    async def test_populates_news_headlines(self) -> None:
        agg, _, _, news_client = _aggregator(
            news=[
                NewsItem(
                    id=1,
                    title="Bitcoin hits ATH",
                    source="CoinDesk",
                    url="https://x",
                    published_at=datetime(2026, 4, 5, 10, tzinfo=timezone.utc),
                )
            ],
        )

        bundle = await agg.collect_for(_market())

        assert len(bundle.news_headlines) == 1
        assert bundle.news_headlines[0]["title"] == "Bitcoin hits ATH"
        assert news_client.calls == [10]

    async def test_populates_technical_indicators_when_enough_history(self) -> None:
        agg, *_ = _aggregator()  # 7d of hourly = 168 candles, plenty for indicators

        bundle = await agg.collect_for(_market())

        assert bundle.rsi_14 is not None
        assert bundle.macd is not None
        assert bundle.bollinger is not None
        assert bundle.atr is not None

    async def test_handles_missing_indicators_when_too_few_candles(self) -> None:
        agg, *_ = _aggregator(klines_1h=_kline_series(5), klines_1d=_kline_series(5))

        bundle = await agg.collect_for(_market())

        assert bundle.rsi_14 is None
        assert bundle.macd is None
        assert bundle.bollinger is None


class _RaisingNews:
    async def get_btc_news(self, limit: int = 10) -> list[NewsItem]:
        raise RuntimeError("simulated CryptoPanic outage")


@pytest.mark.asyncio
async def test_aggregator_returns_empty_news_when_news_client_raises() -> None:
    """News is best-effort; a 5xx or schema drift must NOT kill prediction (PRD §3.2.4)."""
    _, binance, fng_client, _news_client = _aggregator()
    aggregator = DataAggregator(binance=binance, fear_greed=fng_client, news=_RaisingNews())

    bundle = await aggregator.collect_for(_market())

    assert bundle.news_headlines == []
    # Other fields must still be populated from binance + fear_greed
    assert bundle.btc_current_price > 0
    assert bundle.fear_greed_index is not None
