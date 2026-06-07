"""Generate executable trading strategies from AI predictions (PRD §3.4).

Pure synchronous computation — no I/O. The caller persists the returned
``Strategy`` separately (StrategyRepository) and the Executor handles
order placement.

Three hard gates apply before any sizing happens:

1. ``abs(edge) >= 0.25`` — AI's probability must differ from the market
   price by at least 25 percentage points. Smaller edges on an efficient
   market like Polymarket are almost certainly noise, not alpha.
2. ``confidence >= 0.6`` — avoid acting on low-quality predictions even
   when they imply a big edge.
3. The AI's ``recommended_action`` must match the sign of the edge
   (buy_yes when edge>0, buy_no when edge<0). A mismatch indicates the
   model disagrees with its own numbers — skip rather than trust the
   inconsistent output.
"""
from __future__ import annotations

from decimal import Decimal

from app.domain.markets import Market
from app.domain.predictions import Prediction
from app.domain.strategies import Strategy

MIN_EDGE = Decimal("0.25")                       # PRD §3.4 default; env-overridable for demo
MIN_CONFIDENCE = Decimal("0.6")
DEFAULT_MAX_POSITION_PCT = Decimal("0.10")       # cap: 10% of vault per trade
DEFAULT_TAKE_PROFIT_FACTOR = Decimal("0.7")
DEFAULT_STOP_LOSS_FACTOR = Decimal("0.5")
DEFAULT_KELLY_MULTIPLIER = Decimal("0.5")        # half-Kelly

_ZERO = Decimal("0")
_ONE = Decimal("1")


class StrategyGenerator:
    def __init__(
        self,
        vault_balance: Decimal,
        *,
        min_edge: Decimal = MIN_EDGE,
        max_position_pct: Decimal = DEFAULT_MAX_POSITION_PCT,
        take_profit_factor: Decimal = DEFAULT_TAKE_PROFIT_FACTOR,
        stop_loss_factor: Decimal = DEFAULT_STOP_LOSS_FACTOR,
        kelly_multiplier: Decimal = DEFAULT_KELLY_MULTIPLIER,
    ) -> None:
        self._vault_balance = vault_balance
        self._min_edge = min_edge
        self._max_position_pct = max_position_pct
        self._tp_factor = take_profit_factor
        self._sl_factor = stop_loss_factor
        self._kelly_mult = kelly_multiplier

    def generate(self, *, prediction: Prediction, market: Market) -> Strategy:
        if prediction.id is None or market.id is None:
            raise ValueError("prediction and market must be persisted (have ids)")

        edge = prediction.predicted_probability - market.current_yes_price
        abs_edge = abs(edge)

        # Gate 1: edge magnitude
        if abs_edge < self._min_edge:
            return _skip(
                prediction, market, edge,
                reason=f"Edge {abs_edge:.1%} < required {self._min_edge:.0%}",
            )

        # Gate 2: confidence
        if prediction.confidence < MIN_CONFIDENCE:
            return _skip(
                prediction, market, edge,
                reason=f"Confidence {prediction.confidence:.1%} < required {MIN_CONFIDENCE:.0%}",
            )

        # Gate 3: alignment between AI's recommendation and edge sign
        expected_action = "buy_yes" if edge > _ZERO else "buy_no"
        if prediction.recommended_action != expected_action:
            return _skip(
                prediction, market, edge,
                reason=(
                    f"AI recommendation '{prediction.recommended_action}' "
                    f"conflicts with edge sign (expected '{expected_action}')"
                ),
            )

        # Sizing
        side: str = "yes" if edge > _ZERO else "no"
        entry_price = market.current_yes_price if side == "yes" else (_ONE - market.current_yes_price)
        win_probability = (
            prediction.predicted_probability
            if side == "yes"
            else (_ONE - prediction.predicted_probability)
        )
        kelly_fraction = _kelly_fraction(entry_price=entry_price, win_probability=win_probability)
        kelly_fraction_adjusted = kelly_fraction * self._kelly_mult
        if kelly_fraction_adjusted < _ZERO:
            kelly_fraction_adjusted = _ZERO

        max_position = self._vault_balance * self._max_position_pct
        kelly_position = kelly_fraction_adjusted * self._vault_balance
        position_size = min(kelly_position, max_position)

        take_profit = entry_price + abs_edge * self._tp_factor
        stop_loss = entry_price - abs_edge * self._sl_factor

        return Strategy(
            prediction_id=prediction.id,
            market_id=market.id,
            action=expected_action,  # type: ignore[arg-type]
            side=side,               # type: ignore[arg-type]
            position_size=position_size,
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            kelly_fraction=kelly_fraction,
            edge=edge,
            skip_reason="",
            status="pending",
        )


def _kelly_fraction(*, entry_price: Decimal, win_probability: Decimal) -> Decimal:
    """Kelly criterion for a binary payoff: ``f = (b·p − q) / b``.

    On Polymarket a share of value ``entry_price`` pays out $1 on win
    and $0 on loss, so ``b = (1 − entry_price) / entry_price`` and
    ``q = 1 − win_probability``.
    """
    if entry_price <= _ZERO or entry_price >= _ONE:
        return _ZERO
    b = (_ONE - entry_price) / entry_price
    p = win_probability
    q = _ONE - p
    return (b * p - q) / b


def _skip(prediction: Prediction, market: Market, edge: Decimal, *, reason: str) -> Strategy:
    return Strategy(
        prediction_id=prediction.id,      # type: ignore[arg-type]
        market_id=market.id,              # type: ignore[arg-type]
        action="skip",
        side=None,
        position_size=_ZERO,
        entry_price=_ZERO,
        take_profit=_ZERO,
        stop_loss=_ZERO,
        kelly_fraction=_ZERO,
        edge=edge,
        skip_reason=reason,
        status="skipped",
    )
