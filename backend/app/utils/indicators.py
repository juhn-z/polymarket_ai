"""Technical indicator computations.

Wraps the ``ta`` library to produce Decimal-typed dataclasses from a
sequence of :class:`app.domain.binance.Kline`. All indicators return
``None`` when the window is longer than the input series (insufficient
history) rather than raising — callers decide how to treat missing values.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands

from app.domain.binance import Kline


@dataclass(frozen=True, slots=True)
class MacdValues:
    macd: Decimal | None
    signal: Decimal | None
    histogram: Decimal | None


@dataclass(frozen=True, slots=True)
class BollingerValues:
    upper: Decimal
    middle: Decimal
    lower: Decimal


@dataclass(frozen=True, slots=True)
class EmaValues:
    ema7: Decimal
    ema25: Decimal
    ema99: Decimal


@dataclass(frozen=True, slots=True)
class Indicators:
    rsi_14: Decimal | None
    macd: MacdValues | None
    bollinger: BollingerValues | None
    ema: EmaValues | None
    atr: Decimal | None


def compute_indicators(klines: Sequence[Kline]) -> Indicators:
    if not klines:
        return Indicators(rsi_14=None, macd=None, bollinger=None, ema=None, atr=None)

    df = pd.DataFrame(
        {
            "high": [float(k.high) for k in klines],
            "low": [float(k.low) for k in klines],
            "close": [float(k.close) for k in klines],
        }
    )
    n = len(df)

    rsi_14 = _last_decimal(RSIIndicator(df["close"], window=14).rsi()) if n >= 15 else None

    macd: MacdValues | None = None
    if n >= 26:
        macd_obj = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        macd = MacdValues(
            macd=_last_decimal(macd_obj.macd()),
            signal=_last_decimal(macd_obj.macd_signal()),
            histogram=_last_decimal(macd_obj.macd_diff()),
        )

    bollinger: BollingerValues | None = None
    if n >= 20:
        bb = BollingerBands(df["close"], window=20, window_dev=2)
        bollinger = BollingerValues(
            upper=_last_decimal(bb.bollinger_hband()),
            middle=_last_decimal(bb.bollinger_mavg()),
            lower=_last_decimal(bb.bollinger_lband()),
        )

    ema: EmaValues | None = None
    if n >= 99:
        ema = EmaValues(
            ema7=_last_decimal(EMAIndicator(df["close"], window=7).ema_indicator()),
            ema25=_last_decimal(EMAIndicator(df["close"], window=25).ema_indicator()),
            ema99=_last_decimal(EMAIndicator(df["close"], window=99).ema_indicator()),
        )

    atr: Decimal | None = None
    if n >= 14:
        atr_series = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
        atr = _last_decimal(atr_series)

    return Indicators(rsi_14=rsi_14, macd=macd, bollinger=bollinger, ema=ema, atr=atr)


def _last_decimal(series: pd.Series) -> Decimal | None:
    if series.empty:
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        return None
    return Decimal(str(value))
