"""Position Monitor — auto-closes open positions on TP/SL/pre-resolution.

Design:
  - ``check_once()`` is the unit-testable workhorse: inspects all active
    strategies once and closes the ones that hit their thresholds.
  - ``run_forever()`` is the long-running loop used in production, driven
    by ``asyncio.create_task`` from the app lifespan.

Pre-resolution close: we hard-close any active position when the current
time is within ``PRE_RESOLUTION_MINUTES`` of the market's target datetime
(set to 12:00 UTC on the resolution date). This avoids getting caught in
low-liquidity whipsaws right before settlement.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from app.adapters.protocols import PolymarketCLOBClient, VaultClient
from app.domain.markets import Market
from app.domain.strategies import Strategy
from app.repositories.market_repository import MarketRepository
from app.repositories.strategy_repository import StrategyRepository
from app.repositories.trade_repository import TradeRepository
from app.services.trade_executor import TradeExecutor, _token_id_for_side

Clock = Callable[[], datetime]
PRE_RESOLUTION_MINUTES = 30
DEFAULT_INTERVAL_SECONDS = 10


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PositionMonitor:
    def __init__(
        self,
        *,
        clob: PolymarketCLOBClient,
        vault: VaultClient,
        strategy_repo: StrategyRepository,
        trade_repo: TradeRepository,
        market_repo: MarketRepository,
        clock: Clock = _utc_now,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._clob = clob
        self._strategies = strategy_repo
        self._trades = trade_repo
        self._markets = market_repo
        self._clock = clock
        self._interval = interval_seconds
        self._executor = TradeExecutor(
            clob=clob,
            vault=vault,
            strategy_repo=strategy_repo,
            trade_repo=trade_repo,
        )

    async def check_once(self) -> int:
        """Inspect all active positions once. Returns the number closed."""
        closed = 0
        for strategy in await self._strategies.list_active():
            if strategy.status != "active":
                continue
            reason = await self._decision_for(strategy)
            if reason is None:
                continue

            market = await self._markets.get_latest_for_date(  # type: ignore[attr-defined]
                strategy_target_date(strategy, await self._markets.list_all())
            ) if False else await self._resolve_market(strategy)
            if market is None:
                continue

            await self._executor.close_position(strategy=strategy, market=market, reason=reason)
            closed += 1
        return closed

    async def run_forever(self) -> None:
        while True:
            try:
                await self.check_once()
            except Exception:  # pragma: no cover - defensive
                # A single failure shouldn't kill the monitor loop.
                pass
            await asyncio.sleep(self._interval)

    async def _decision_for(self, strategy: Strategy) -> str | None:
        if strategy.side is None:
            return None
        market = await self._resolve_market(strategy)
        if market is None:
            return None

        if _within_pre_resolution_window(self._clock(), market.target_date):
            return "pre_resolution"

        token_id = _token_id_for_side(market, strategy.side)
        price = await self._clob.get_current_price(token_id)
        if price >= strategy.take_profit:
            return "take_profit"
        if price <= strategy.stop_loss:
            return "stop_loss"
        return None

    async def _resolve_market(self, strategy: Strategy) -> Market | None:
        # Strategies are 1:1 with markets in v1 — pick the one referenced by id.
        markets = await self._markets.list_all()
        for m in markets:
            if m.id == strategy.market_id:
                return m
        return None


def strategy_target_date(strategy: Strategy, markets):  # pragma: no cover - unused helper
    for m in markets:
        if m.id == strategy.market_id:
            return m.target_date
    return None


def _within_pre_resolution_window(now: datetime, target_date) -> bool:
    resolution_at = datetime.combine(target_date, time(12, 0), tzinfo=timezone.utc)
    return timedelta(0) <= (resolution_at - now) <= timedelta(minutes=PRE_RESOLUTION_MINUTES)
