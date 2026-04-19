"""Unit tests for technical indicator calculations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.binance import Kline
from app.utils.indicators import Indicators, compute_indicators


def _kline_series(closes: list[float]) -> list[Kline]:
    """Build a minimal kline series where only close matters for most indicators."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out: list[Kline] = []
    for i, close in enumerate(closes):
        d = Decimal(str(close))
        out.append(
            Kline(
                open_time=base + timedelta(hours=i),
                close_time=base + timedelta(hours=i, minutes=59, seconds=59),
                open=d,
                high=d + Decimal("5"),
                low=d - Decimal("5"),
                close=d,
                volume=Decimal("100"),
            )
        )
    return out


class TestIndicators:
    def test_returns_none_fields_when_insufficient_data(self) -> None:
        result = compute_indicators(_kline_series([100.0, 101.0, 102.0]))
        # With only 3 candles none of the 14/20/26 window indicators can be computed.
        assert result.rsi_14 is None
        assert result.macd is None
        assert result.bollinger is None
        assert result.atr is None

    def test_rsi_at_100_for_strictly_rising_series(self) -> None:
        closes = [float(i) for i in range(100, 140)]  # 40 candles, monotonic up
        result = compute_indicators(_kline_series(closes))
        assert result.rsi_14 is not None
        # Strictly rising closes → no downside → RSI saturates near 100.
        assert result.rsi_14 > Decimal("95")

    def test_rsi_below_50_for_falling_series(self) -> None:
        closes = [float(140 - i) for i in range(40)]
        result = compute_indicators(_kline_series(closes))
        assert result.rsi_14 is not None
        assert result.rsi_14 < Decimal("50")

    def test_bollinger_bands_surround_sma(self) -> None:
        closes = [100.0 + i * 0.5 for i in range(40)]
        result = compute_indicators(_kline_series(closes))
        assert result.bollinger is not None
        assert result.bollinger.upper > result.bollinger.middle > result.bollinger.lower

    def test_ema_7_responds_faster_than_ema_99(self) -> None:
        """EMA(7) should track recent jump more aggressively than EMA(99)."""
        closes = [100.0] * 100 + [200.0] * 20  # step up
        result = compute_indicators(_kline_series(closes))
        assert result.ema is not None
        assert result.ema.ema7 > result.ema.ema99

    def test_returns_dataclass_with_all_fields_populated_when_sufficient_history(self) -> None:
        closes = [100.0 + i for i in range(100)]
        result = compute_indicators(_kline_series(closes))
        assert isinstance(result, Indicators)
        assert result.rsi_14 is not None
        assert result.macd is not None
        assert result.macd.macd is not None
        assert result.macd.signal is not None
        assert result.bollinger is not None
        assert result.ema is not None
        assert result.atr is not None
