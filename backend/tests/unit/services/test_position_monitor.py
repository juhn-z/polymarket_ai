"""Unit tests for PositionMonitor.check_once."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.markets import Market
from app.domain.strategies import Strategy
from app.services.position_monitor import PositionMonitor
from tests.fakes.fake_market_repository import FakeMarketRepository
from tests.fakes.fake_polymarket_clob import FakePolymarketCLOBClient
from tests.fakes.fake_strategy_repository import FakeStrategyRepository
from tests.fakes.fake_trade_repository import FakeTradeRepository
from tests.fakes.fake_vault import FakeVaultClient

NOW = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)  # 24h before target
TARGET = date(2026, 4, 7)


def _clock():
    return NOW


async def _setup_active_position(*, tp: str = "0.66", sl: str = "0.30"):
    """Build a fully wired environment with one active buy-NO strategy."""
    clob = FakePolymarketCLOBClient()
    vault = FakeVaultClient()
    market_repo = FakeMarketRepository()
    strat_repo = FakeStrategyRepository()
    trade_repo = FakeTradeRepository()

    market = await market_repo.save(
        Market(
            polymarket_condition_id="0xabc",
            polymarket_token_id="yes-abc",
            event_slug="btc",
            question="Bitcoin above 66000 on April 7?",
            price_threshold=66000,
            scan_date=date(2026, 4, 5),
            target_date=TARGET,
            current_yes_price=Decimal("0.55"),
            current_no_price=Decimal("0.45"),
            selected_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
        )
    )
    strategy = await strat_repo.save(
        Strategy(
            prediction_id=1,
            market_id=market.id,  # type: ignore[arg-type]
            action="buy_no",
            side="no",
            position_size=Decimal("500"),
            entry_price=Decimal("0.45"),
            take_profit=Decimal(tp),
            stop_loss=Decimal(sl),
            kelly_fraction=Decimal("0.4"),
            edge=Decimal("-0.30"),
            skip_reason="",
            status="pending",
        )
    )
    # Simulate the opening buy trade was filled.
    from app.services.trade_executor import TradeExecutor
    exec_ = TradeExecutor(clob=clob, vault=vault, strategy_repo=strat_repo, trade_repo=trade_repo)
    await exec_.execute(strategy=strategy, market=market)

    return clob, vault, market_repo, strat_repo, trade_repo


@pytest.fixture
async def env():
    return await _setup_active_position()


class TestPositionMonitor:
    async def test_closes_on_take_profit(self, env) -> None:
        clob, vault, market_repo, strat_repo, trade_repo = env
        clob.set_price("no-abc", Decimal("0.67"))   # >= TP 0.66

        monitor = PositionMonitor(
            clob=clob, vault=vault,
            strategy_repo=strat_repo, trade_repo=trade_repo,
            market_repo=market_repo,
            clock=_clock,
        )
        closed_count = await monitor.check_once()

        assert closed_count == 1
        active = await strat_repo.list_active()
        assert active == []
        last = await trade_repo.list_all()
        assert last[0].action == "sell"
        assert last[0].close_reason == "take_profit"

    async def test_closes_on_stop_loss(self, env) -> None:
        clob, vault, market_repo, strat_repo, trade_repo = env
        clob.set_price("no-abc", Decimal("0.29"))   # <= SL 0.30

        monitor = PositionMonitor(
            clob=clob, vault=vault,
            strategy_repo=strat_repo, trade_repo=trade_repo,
            market_repo=market_repo,
            clock=_clock,
        )
        closed = await monitor.check_once()

        assert closed == 1
        last = await trade_repo.list_all()
        assert last[0].close_reason == "stop_loss"

    async def test_closes_pre_resolution_within_30min(self, env) -> None:
        clob, vault, market_repo, strat_repo, trade_repo = env
        # Current price neither TP nor SL but we are < 30 min before resolution.
        clob.set_price("no-abc", Decimal("0.50"))

        # Resolution = TARGET + noon UTC; set clock to 20 minutes before that.
        pre_resolution_clock = lambda: datetime.combine(
            TARGET, datetime.min.time(), tzinfo=timezone.utc,
        ).replace(hour=11, minute=40)

        monitor = PositionMonitor(
            clob=clob, vault=vault,
            strategy_repo=strat_repo, trade_repo=trade_repo,
            market_repo=market_repo,
            clock=pre_resolution_clock,
        )
        closed = await monitor.check_once()

        assert closed == 1
        last = await trade_repo.list_all()
        assert last[0].close_reason == "pre_resolution"

    async def test_leaves_position_open_within_band(self, env) -> None:
        clob, vault, market_repo, strat_repo, trade_repo = env
        clob.set_price("no-abc", Decimal("0.50"))   # inside SL..TP

        monitor = PositionMonitor(
            clob=clob, vault=vault,
            strategy_repo=strat_repo, trade_repo=trade_repo,
            market_repo=market_repo,
            clock=_clock,
        )
        closed = await monitor.check_once()

        assert closed == 0
        still_active = await strat_repo.list_active()
        assert len(still_active) == 1

    async def test_skips_strategy_without_active_status(self) -> None:
        clob = FakePolymarketCLOBClient()
        vault = FakeVaultClient()
        market_repo = FakeMarketRepository()
        strat_repo = FakeStrategyRepository()
        trade_repo = FakeTradeRepository()
        monitor = PositionMonitor(
            clob=clob, vault=vault,
            strategy_repo=strat_repo, trade_repo=trade_repo,
            market_repo=market_repo,
            clock=_clock,
        )
        # No active strategies → should be a no-op.
        assert await monitor.check_once() == 0
