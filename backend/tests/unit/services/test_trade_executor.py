"""Unit tests for TradeExecutor — opens and closes Polymarket positions."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.domain.markets import Market
from app.domain.strategies import Strategy
from app.domain.trades import Trade
from app.services.trade_executor import TradeExecutor
from tests.fakes.fake_polymarket_clob import FakePolymarketCLOBClient
from tests.fakes.fake_strategy_repository import FakeStrategyRepository
from tests.fakes.fake_trade_repository import FakeTradeRepository
from tests.fakes.fake_vault import FakeVaultClient


def _market(*, market_id: int = 1, yes_price: str = "0.55") -> Market:
    return Market(
        id=market_id,
        polymarket_condition_id="0xabc",
        polymarket_token_id="yes-token",
        event_slug="btc-above",
        question="Bitcoin above 66000 on April 7?",
        price_threshold=66000,
        scan_date=date(2026, 4, 5),
        target_date=date(2026, 4, 7),
        current_yes_price=Decimal(yes_price),
        current_no_price=Decimal("1") - Decimal(yes_price),
        selected_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
    )


def _pending_buy_no_strategy(*, strategy_id: int = 1, market_id: int = 1) -> Strategy:
    return Strategy(
        id=strategy_id,
        prediction_id=101,
        market_id=market_id,
        action="buy_no",
        side="no",
        position_size=Decimal("500"),      # $500 USDC
        entry_price=Decimal("0.45"),
        take_profit=Decimal("0.66"),
        stop_loss=Decimal("0.30"),
        kelly_fraction=Decimal("0.4"),
        edge=Decimal("-0.30"),
        skip_reason="",
        status="pending",
    )


def _active_buy_no_strategy() -> Strategy:
    s = _pending_buy_no_strategy()
    s.status = "active"
    return s


class TestExecuteOpen:
    async def test_withdraws_from_vault_and_places_clob_order(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient(available_balance=Decimal("100000"))
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        exec_ = TradeExecutor(
            clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo,
        )

        strategy = await strat_repo.save(_pending_buy_no_strategy())
        market = _market()

        trade = await exec_.execute(strategy=strategy, market=market)

        # Vault.withdraw_to_strategy called with the position size.
        assert vault.withdraw_calls == [Decimal("500")]

        # CLOB order placed on the NO token at entry_price.
        assert len(clob.place_calls) == 1
        call = clob.place_calls[0]
        assert call["token_id"] == "no-token"
        assert call["side"] == "buy"
        assert call["price"] == Decimal("0.45")

        # Trade record created.
        assert isinstance(trade, Trade)
        assert trade.strategy_id == strategy.id
        assert trade.side == "no"
        assert trade.action == "buy"
        assert trade.status == "filled"
        assert trade.price == Decimal("0.45")

    async def test_uses_yes_token_for_buy_yes_strategy(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient()
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        exec_ = TradeExecutor(
            clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo,
        )

        s = _pending_buy_no_strategy()
        s.action = "buy_yes"
        s.side = "yes"
        s.entry_price = Decimal("0.55")
        saved = await strat_repo.save(s)

        await exec_.execute(strategy=saved, market=_market())

        assert clob.place_calls[0]["token_id"] == "yes-token"

    async def test_skipped_strategy_is_no_op(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient()
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        exec_ = TradeExecutor(
            clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo,
        )

        s = _pending_buy_no_strategy()
        s.action = "skip"
        s.status = "skipped"
        s.position_size = Decimal("0")
        saved = await strat_repo.save(s)

        with pytest.raises(ValueError, match="skip"):
            await exec_.execute(strategy=saved, market=_market())

        assert vault.withdraw_calls == []
        assert clob.place_calls == []

    async def test_promotes_strategy_status_to_active_on_fill(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient()
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        exec_ = TradeExecutor(
            clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo,
        )

        saved = await strat_repo.save(_pending_buy_no_strategy())
        await exec_.execute(strategy=saved, market=_market())

        reloaded = await strat_repo.get_by_id(saved.id)  # type: ignore[arg-type]
        assert reloaded is not None
        assert reloaded.status == "active"
        assert reloaded.executed_at is not None


class TestClosePosition:
    async def test_sells_all_shares_and_returns_proceeds_to_vault(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient()
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        exec_ = TradeExecutor(
            clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo,
        )

        # First, open the position.
        saved = await strat_repo.save(_pending_buy_no_strategy())
        await exec_.execute(strategy=saved, market=_market())
        original_vault_balance = await vault.available_balance()

        # Set the current price above TP so close fetches a favorable price.
        clob.set_price("no-token", Decimal("0.66"))
        reloaded = await strat_repo.get_by_id(saved.id)  # type: ignore[arg-type]
        assert reloaded is not None

        close_trade = await exec_.close_position(
            strategy=reloaded, market=_market(), reason="take_profit",
        )

        # A sell order was placed.
        sell_calls = [c for c in clob.place_calls if c["side"] == "sell"]
        assert len(sell_calls) == 1
        assert sell_calls[0]["token_id"] == "no-token"

        # Proceeds deposited back to vault.
        assert len(vault.deposit_calls) == 1
        # Strategy now closed.
        final = await strat_repo.get_by_id(saved.id)  # type: ignore[arg-type]
        assert final is not None
        assert final.status == "closed"

        assert close_trade.action == "sell"
        assert close_trade.close_reason == "take_profit"
        assert close_trade.pnl is not None

    async def test_cannot_close_strategy_without_active_position(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient()
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        exec_ = TradeExecutor(
            clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo,
        )

        # Strategy not executed yet (status=pending, no open position).
        saved = await strat_repo.save(_pending_buy_no_strategy())

        with pytest.raises(ValueError):
            await exec_.close_position(
                strategy=saved, market=_market(), reason="manual",
            )
