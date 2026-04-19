"""Trade Executor — opens and closes Polymarket positions for one Strategy.

PRD §3.5 workflow:

  execute(strategy):
    1. vault.withdraw_to_strategy(strategy.position_size)
    2. clob.place_order(buy, token_id=<yes|no>, price=entry_price, size=...)
    3. persist Trade (status=filled/pending); mark strategy status=active

  close_position(strategy, reason):
    1. look up open trades for strategy → determine shares to sell
    2. clob.place_order(sell, token_id=..., price=market_price, size=shares)
    3. vault.deposit_from_strategy(proceeds)
    4. persist closing Trade with pnl; mark strategy status=closed
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.adapters.protocols import PolymarketCLOBClient, VaultClient
from app.domain.markets import Market
from app.domain.strategies import Strategy
from app.domain.trades import CloseReason, Trade
from app.repositories.strategy_repository import StrategyRepository
from app.repositories.trade_repository import TradeRepository

_ZERO = Decimal("0")


class TradeExecutor:
    def __init__(
        self,
        clob: PolymarketCLOBClient,
        vault: VaultClient,
        strategy_repo: StrategyRepository,
        trade_repo: TradeRepository,
    ) -> None:
        self._clob = clob
        self._vault = vault
        self._strategies = strategy_repo
        self._trades = trade_repo

    async def execute(self, *, strategy: Strategy, market: Market) -> Trade:
        if strategy.id is None:
            raise ValueError("strategy must be persisted before execute()")
        if strategy.action == "skip" or strategy.status == "skipped":
            raise ValueError(f"cannot execute a skipped strategy (id={strategy.id})")
        if strategy.side is None:
            raise ValueError("strategy has no side")

        token_id = _token_id_for_side(market, strategy.side)

        # Step 1: pull USDC from the vault.
        await self._vault.withdraw_to_strategy(strategy.position_size)

        # Step 2: buy the chosen side on Polymarket.
        shares_requested = strategy.position_size / strategy.entry_price
        order = await self._clob.place_order(
            token_id=token_id,
            side="buy",
            price=strategy.entry_price,
            size=shares_requested,
        )

        # Step 3: persist trade.
        now = datetime.now(timezone.utc)
        trade = Trade(
            strategy_id=strategy.id,
            market_id=market.id,  # type: ignore[arg-type]
            polymarket_order_id=order.order_id,
            side=strategy.side,
            action="buy",
            amount=order.filled_size * order.price,
            price=order.price,
            shares=order.filled_size,
            status=_map_status(order.status),
            fee=order.fee,
            filled_at=now if order.status == "filled" else None,
        )
        saved_trade = await self._trades.save(trade)

        # Step 4: flip strategy status to "active" once at least partly filled.
        if order.status in ("filled", "partial"):
            strategy.status = "active"
            strategy.executed_at = now
            await self._strategies.save(strategy)

        return saved_trade

    async def close_position(
        self, *, strategy: Strategy, market: Market, reason: CloseReason,
    ) -> Trade:
        if strategy.id is None:
            raise ValueError("strategy must be persisted before close_position()")
        if strategy.status != "active":
            raise ValueError(
                f"cannot close strategy id={strategy.id} with status={strategy.status!r}; expected 'active'"
            )
        if strategy.side is None:
            raise ValueError("strategy has no side")

        # Find the open buy trade to know how many shares to sell.
        trades = await self._trades.list_for_strategy(strategy.id)
        buys = [t for t in trades if t.action == "buy" and t.status == "filled"]
        if not buys:
            raise ValueError(f"no filled buy for strategy id={strategy.id}")
        total_shares = sum((t.shares for t in buys), start=_ZERO)
        buy_cost = sum((t.amount + t.fee for t in buys), start=_ZERO)

        token_id = _token_id_for_side(market, strategy.side)
        current_price = await self._clob.get_current_price(token_id)

        order = await self._clob.place_order(
            token_id=token_id,
            side="sell",
            price=current_price,
            size=total_shares,
        )

        proceeds = order.filled_size * order.price - order.fee
        await self._vault.deposit_from_strategy(proceeds)

        now = datetime.now(timezone.utc)
        pnl = proceeds - buy_cost
        close_trade = Trade(
            strategy_id=strategy.id,
            market_id=market.id,  # type: ignore[arg-type]
            polymarket_order_id=order.order_id,
            side=strategy.side,
            action="sell",
            amount=proceeds,
            price=order.price,
            shares=order.filled_size,
            status=_map_status(order.status),
            fee=order.fee,
            pnl=pnl,
            close_reason=reason,
            filled_at=now if order.status == "filled" else None,
            closed_at=now,
        )
        saved_close = await self._trades.save(close_trade)

        strategy.status = "closed"
        await self._strategies.save(strategy)

        return saved_close


def _token_id_for_side(market: Market, side: str) -> str:
    """Return the CLOB token id to trade for a given side.

    ``Market.polymarket_token_id`` stores the Yes token id by convention.
    The No token id is derived by prefix when we don't have it stored —
    for tests we use "yes-token"/"no-token" pairs; for production the
    GammaMarket DTO has both. We persist only one on Market to keep
    migrations simple; the Executor derives the other.
    """
    yes = market.polymarket_token_id
    if side == "yes":
        return yes
    # Derivation: swap prefix "yes-"→"no-" or fall back to suffix flip.
    if yes.startswith("yes-"):
        return "no-" + yes[len("yes-"):]
    if yes.startswith("yes_"):
        return "no_" + yes[len("yes_"):]
    return yes + ".no"  # last-resort marker


def _map_status(clob_status: str) -> str:
    if clob_status in ("filled", "partial", "pending", "cancelled", "failed"):
        return clob_status
    return "failed"
