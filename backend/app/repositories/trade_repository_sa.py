"""SQLAlchemy implementation of TradeRepository."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trades import CloseReason, Trade, TradeAction, TradeSide, TradeStatus
from app.models.trade import TradeORM

_ACTIVE_STATUSES = ("pending", "partial")


class SqlAlchemyTradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, trade: Trade) -> Trade:
        if trade.id is None:
            row = TradeORM(
                strategy_id=trade.strategy_id,
                market_id=trade.market_id,
                polymarket_order_id=trade.polymarket_order_id,
                side=trade.side,
                action=trade.action,
                amount=trade.amount,
                price=trade.price,
                shares=trade.shares,
                status=trade.status,
                fee=trade.fee,
                pnl=trade.pnl,
                close_reason=trade.close_reason,
                filled_at=trade.filled_at,
                closed_at=trade.closed_at,
            )
            self._session.add(row)
            await self._session.flush()
            return _to_domain(row)

        row = await self._session.get(TradeORM, trade.id)
        if row is None:
            raise ValueError(f"Trade id={trade.id} not found")
        row.status = trade.status
        row.pnl = trade.pnl
        row.closed_at = trade.closed_at
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, trade_id: int) -> Trade | None:
        row = await self._session.get(TradeORM, trade_id)
        return _to_domain(row) if row else None

    async def list_active(self) -> list[Trade]:
        stmt = (
            select(TradeORM)
            .where(TradeORM.status.in_(_ACTIVE_STATUSES))
            .order_by(TradeORM.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_all(self) -> list[Trade]:
        stmt = select(TradeORM).order_by(TradeORM.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_for_strategy(self, strategy_id: int) -> list[Trade]:
        stmt = (
            select(TradeORM)
            .where(TradeORM.strategy_id == strategy_id)
            .order_by(TradeORM.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


def _to_domain(row: TradeORM) -> Trade:
    return Trade(
        id=row.id,
        strategy_id=row.strategy_id,
        market_id=row.market_id,
        polymarket_order_id=row.polymarket_order_id,
        side=_cast_side(row.side),
        action=_cast_action(row.action),
        amount=row.amount,
        price=row.price,
        shares=row.shares,
        status=_cast_status(row.status),
        fee=row.fee,
        pnl=row.pnl,
        close_reason=_cast_close_reason(row.close_reason),
        filled_at=row.filled_at,
        closed_at=row.closed_at,
        created_at=row.created_at,
    )


def _cast_side(value: str) -> TradeSide:
    if value not in ("yes", "no"):
        raise ValueError(f"unexpected side: {value}")
    return value  # type: ignore[return-value]


def _cast_action(value: str) -> TradeAction:
    if value not in ("buy", "sell"):
        raise ValueError(f"unexpected action: {value}")
    return value  # type: ignore[return-value]


def _cast_status(value: str) -> TradeStatus:
    if value not in ("pending", "filled", "partial", "cancelled", "failed"):
        raise ValueError(f"unexpected status: {value}")
    return value  # type: ignore[return-value]


def _cast_close_reason(value: str | None) -> CloseReason | None:
    if value is None:
        return None
    if value not in ("take_profit", "stop_loss", "pre_resolution", "manual"):
        raise ValueError(f"unexpected close_reason: {value}")
    return value  # type: ignore[return-value]
