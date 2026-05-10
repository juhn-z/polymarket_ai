"""Aggregate multi-source market data for AI prediction input."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any

from app.adapters.protocols import BinanceClient, FearGreedClient, NewsClient
from app.domain.markets import Market
from app.utils.indicators import (
    BollingerValues,
    EmaValues,
    Indicators,
    MacdValues,
    compute_indicators,
)

BTC_SYMBOL = "BTCUSDT"
INTERVAL_1H = "1h"
INTERVAL_1D = "1d"
KLINE_LIMIT_1H = 24 * 7   # last 7 days of hourly candles
KLINE_LIMIT_1D = 30       # last 30 daily candles
FNG_DAYS = 7
NEWS_LIMIT = 10


@dataclass(slots=True)
class MarketDataBundle:
    """All the data the AI predictor consumes for one scan/prediction cycle."""
    timestamp: datetime
    btc_current_price: Decimal
    target_price: int
    target_datetime: datetime

    # 24h change from Binance ticker
    high_24h: Decimal
    low_24h: Decimal
    volume_24h: Decimal
    price_change_24h: Decimal   # percentage

    # Technical indicators (None = insufficient history)
    rsi_14: Decimal | None
    macd: MacdValues | None
    bollinger: BollingerValues | None
    ema: EmaValues | None
    atr: Decimal | None

    # Sentiment
    fear_greed_index: int | None
    fear_greed_label: str | None
    fear_greed_trend_7d: list[int] = field(default_factory=list)

    # News
    news_headlines: list[dict[str, Any]] = field(default_factory=list)


class DataAggregator:
    def __init__(
        self,
        binance: BinanceClient,
        fear_greed: FearGreedClient,
        news: NewsClient,
    ) -> None:
        self._binance = binance
        self._fear_greed = fear_greed
        self._news = news

    async def collect_for(self, market: Market) -> MarketDataBundle:
        klines_1h = await self._binance.get_klines(BTC_SYMBOL, INTERVAL_1H, KLINE_LIMIT_1H)
        klines_1d = await self._binance.get_klines(BTC_SYMBOL, INTERVAL_1D, KLINE_LIMIT_1D)
        ticker = await self._binance.get_24h_ticker(BTC_SYMBOL)
        fng_points = await self._fear_greed.get_index(days=FNG_DAYS)
        try:
            news_items = await self._news.get_btc_news(limit=NEWS_LIMIT)
        except Exception:
            # News is optional. CryptoPanic outages, missing keys, or schema
            # drift should not block the daily prediction (PRD §3.2.4 — news
            # is best-effort context, not a hard input).
            news_items = []

        indicators = compute_indicators(klines_1h)

        latest_fng = fng_points[0] if fng_points else None
        target_dt = datetime.combine(market.target_date, time(12, 0), tzinfo=timezone.utc)

        return MarketDataBundle(
            timestamp=datetime.now(timezone.utc),
            btc_current_price=ticker.last_price,
            target_price=market.price_threshold,
            target_datetime=target_dt,
            high_24h=ticker.high_price,
            low_24h=ticker.low_price,
            volume_24h=ticker.volume,
            price_change_24h=ticker.price_change_percent,
            rsi_14=indicators.rsi_14,
            macd=indicators.macd,
            bollinger=indicators.bollinger,
            ema=indicators.ema,
            atr=indicators.atr,
            fear_greed_index=latest_fng.value if latest_fng else None,
            fear_greed_label=latest_fng.label if latest_fng else None,
            fear_greed_trend_7d=[p.value for p in fng_points],
            news_headlines=[
                {
                    "id": item.id,
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "published_at": item.published_at.isoformat(),
                }
                for item in news_items
            ],
        )


__all__ = ["DataAggregator", "MarketDataBundle"]
