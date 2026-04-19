"""Unit tests for StrategyGenerator — pure-function TDD (PRD §3.4)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.domain.markets import Market
from app.domain.predictions import Prediction
from app.domain.strategies import Strategy
from app.services.strategy_generator import StrategyGenerator

MIN_EDGE = Decimal("0.25")
MIN_CONFIDENCE = Decimal("0.6")
MAX_POSITION_PCT = Decimal("0.10")
TAKE_PROFIT_FACTOR = Decimal("0.7")
STOP_LOSS_FACTOR = Decimal("0.5")
VAULT_BALANCE = Decimal("100000")   # $100k test vault


def _market(*, market_yes_price: str = "0.55", market_id: int = 1) -> Market:
    yes = Decimal(market_yes_price)
    return Market(
        id=market_id,
        polymarket_condition_id="0xabc",
        polymarket_token_id="yes-token",
        event_slug="btc-above",
        question="Bitcoin above?",
        price_threshold=66000,
        scan_date=date(2026, 4, 5),
        target_date=date(2026, 4, 7),
        current_yes_price=yes,
        current_no_price=Decimal("1") - yes,
        selected_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
    )


def _prediction(
    *,
    predicted_probability: str = "0.25",
    confidence: str = "0.78",
    recommended_action: str = "buy_no",
    market_probability: str = "0.55",
    prediction_id: int = 101,
    market_id: int = 1,
) -> Prediction:
    predicted = Decimal(predicted_probability)
    market = Decimal(market_probability)
    return Prediction(
        id=prediction_id,
        market_id=market_id,
        predicted_probability=predicted,
        confidence=Decimal(confidence),
        direction="bearish" if predicted < market else "bullish",
        key_factors=["a", "b"],
        risk_factors=["r1", "r2"],
        technical_analysis="ta",
        sentiment_analysis="sa",
        news_impact="ni",
        onchain_analysis="oa",
        reasoning="r",
        recommended_action=recommended_action,  # type: ignore[arg-type]
        market_probability=market,
        edge=predicted - market,
        model_version="gpt-5.4",
        prompt_version="v1.0",
        seed=42,
        raw_request={},
        raw_response={},
        data_snapshot={},
    )


class TestHardGates:
    def test_skip_when_edge_below_25pct(self) -> None:
        """predicted=0.42, market=0.55 → |edge|=0.13 < 0.25 → skip"""
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        s = gen.generate(
            prediction=_prediction(
                predicted_probability="0.42",
                confidence="0.90",
                recommended_action="buy_no",
            ),
            market=_market(market_yes_price="0.55"),
        )
        assert s.action == "skip"
        assert "edge" in s.skip_reason.lower()
        assert s.status == "skipped"

    def test_skip_when_confidence_below_60pct(self) -> None:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        s = gen.generate(
            prediction=_prediction(
                predicted_probability="0.25",
                confidence="0.55",
                recommended_action="buy_no",
            ),
            market=_market(market_yes_price="0.55"),
        )
        assert s.action == "skip"
        assert "confidence" in s.skip_reason.lower()

    def test_skip_when_ai_recommendation_misaligned_with_edge_direction(self) -> None:
        """edge = 0.25 - 0.55 = -0.30 (favors NO), but AI says buy_yes → skip."""
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        s = gen.generate(
            prediction=_prediction(
                predicted_probability="0.25",
                confidence="0.80",
                recommended_action="buy_yes",  # misaligned
            ),
            market=_market(market_yes_price="0.55"),
        )
        assert s.action == "skip"
        assert "conflict" in s.skip_reason.lower() or "mis" in s.skip_reason.lower()

    def test_skip_when_ai_says_skip_even_if_edge_hits(self) -> None:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        s = gen.generate(
            prediction=_prediction(
                predicted_probability="0.25",
                confidence="0.80",
                recommended_action="skip",
            ),
            market=_market(market_yes_price="0.55"),
        )
        assert s.action == "skip"


class TestBuyNo:
    """edge < 0 → buy NO side (AI thinks market too bullish)."""

    def _gen(self, predicted: str = "0.25", market_yes: str = "0.55") -> Strategy:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        return gen.generate(
            prediction=_prediction(predicted_probability=predicted, recommended_action="buy_no"),
            market=_market(market_yes_price=market_yes),
        )

    def test_action_and_side(self) -> None:
        s = self._gen()
        assert s.action == "buy_no"
        assert s.side == "no"

    def test_entry_price_is_no_token_price(self) -> None:
        s = self._gen(market_yes="0.55")
        # buy NO ⇒ entry at (1 - yes_price) = 0.45
        assert s.entry_price == Decimal("0.45")

    def test_take_profit_above_entry(self) -> None:
        """For a NO-side buy, TP is entry + |edge|*0.7 (NO token appreciates toward $1)."""
        s = self._gen()
        abs_edge = Decimal("0.30")
        expected_tp = Decimal("0.45") + abs_edge * TAKE_PROFIT_FACTOR
        assert s.take_profit == expected_tp

    def test_stop_loss_below_entry(self) -> None:
        s = self._gen()
        abs_edge = Decimal("0.30")
        expected_sl = Decimal("0.45") - abs_edge * STOP_LOSS_FACTOR
        assert s.stop_loss == expected_sl


class TestBuyYes:
    """edge > 0 → buy YES side (AI thinks market too bearish)."""

    def _gen(self, predicted: str = "0.90", market_yes: str = "0.60") -> Strategy:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        return gen.generate(
            prediction=_prediction(
                predicted_probability=predicted,
                market_probability=market_yes,
                recommended_action="buy_yes",
            ),
            market=_market(market_yes_price=market_yes),
        )

    def test_action_and_side(self) -> None:
        s = self._gen()
        assert s.action == "buy_yes"
        assert s.side == "yes"

    def test_entry_price_is_yes_token_price(self) -> None:
        s = self._gen(market_yes="0.60")
        assert s.entry_price == Decimal("0.60")


class TestPositionSizing:
    def test_position_capped_at_max_pct_of_vault(self) -> None:
        """High-conviction trade should still cap at 10% of vault balance."""
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        # very confident, huge edge
        s = gen.generate(
            prediction=_prediction(
                predicted_probability="0.90",
                confidence="0.99",
                market_probability="0.20",
                recommended_action="buy_yes",
            ),
            market=_market(market_yes_price="0.20"),
        )
        assert s.action == "buy_yes"
        assert s.position_size <= VAULT_BALANCE * MAX_POSITION_PCT
        assert s.position_size > 0

    def test_kelly_fraction_is_positive_for_profitable_bet(self) -> None:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        s = gen.generate(
            prediction=_prediction(
                predicted_probability="0.25",
                market_probability="0.55",
                recommended_action="buy_no",
            ),
            market=_market(market_yes_price="0.55"),
        )
        assert s.kelly_fraction > Decimal("0")

    def test_half_kelly_applied(self) -> None:
        """Position size uses half-Kelly, not full Kelly."""
        # Large max_position_pct so neither run is clipped by the cap —
        # we're isolating the Kelly multiplier's effect.
        no_cap = Decimal("1")
        gen_half = StrategyGenerator(
            vault_balance=Decimal("10"), kelly_multiplier=Decimal("0.5"), max_position_pct=no_cap,
        )
        gen_full = StrategyGenerator(
            vault_balance=Decimal("10"), kelly_multiplier=Decimal("1.0"), max_position_pct=no_cap,
        )
        pred = _prediction(
            predicted_probability="0.85",
            market_probability="0.50",
            confidence="0.80",
            recommended_action="buy_yes",
        )
        market = _market(market_yes_price="0.50")

        s_half = gen_half.generate(prediction=pred, market=market)
        s_full = gen_full.generate(prediction=pred, market=market)

        assert s_full.kelly_fraction > Decimal("0")
        assert s_half.position_size < s_full.position_size
        # Exactly half — up to rounding noise.
        assert abs(s_half.position_size * Decimal("2") - s_full.position_size) < Decimal("0.0001")


class TestPersistenceFields:
    def test_strategy_carries_references_to_parents(self) -> None:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        pred = _prediction(prediction_id=555, market_id=777)
        market = _market(market_id=777)
        s = gen.generate(prediction=pred, market=market)
        assert s.prediction_id == 555
        assert s.market_id == 777

    def test_buy_strategy_has_pending_status(self) -> None:
        gen = StrategyGenerator(vault_balance=VAULT_BALANCE)
        s = gen.generate(
            prediction=_prediction(recommended_action="buy_no"),
            market=_market(market_yes_price="0.55"),
        )
        assert s.status == "pending"
