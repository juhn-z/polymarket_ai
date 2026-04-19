"""SQLAlchemy implementation of StrategyRepository."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.strategies import Strategy, StrategyAction, StrategySide, StrategyStatus
from app.models.strategy import StrategyORM

_ACTIVE_STATUSES = ("pending", "executing", "active")


class SqlAlchemyStrategyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, strategy: Strategy) -> Strategy:
        if strategy.id is None:
            row = StrategyORM(
                prediction_id=strategy.prediction_id,
                market_id=strategy.market_id,
                action=strategy.action,
                side=strategy.side,
                position_size=strategy.position_size,
                entry_price=strategy.entry_price,
                take_profit=strategy.take_profit,
                stop_loss=strategy.stop_loss,
                kelly_fraction=strategy.kelly_fraction,
                edge=strategy.edge,
                skip_reason=strategy.skip_reason,
                status=strategy.status,
                executed_at=strategy.executed_at,
            )
            self._session.add(row)
            await self._session.flush()
            return _to_domain(row)

        row = await self._session.get(StrategyORM, strategy.id)
        if row is None:
            raise ValueError(f"Strategy id={strategy.id} not found")
        row.status = strategy.status
        row.executed_at = strategy.executed_at
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, strategy_id: int) -> Strategy | None:
        row = await self._session.get(StrategyORM, strategy_id)
        return _to_domain(row) if row else None

    async def list_active(self) -> list[Strategy]:
        stmt = (
            select(StrategyORM)
            .where(StrategyORM.status.in_(_ACTIVE_STATUSES))
            .order_by(StrategyORM.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def list_all(self) -> list[Strategy]:
        stmt = select(StrategyORM).order_by(StrategyORM.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def get_latest_for_market(self, market_id: int) -> Strategy | None:
        stmt = (
            select(StrategyORM)
            .where(StrategyORM.market_id == market_id)
            .order_by(StrategyORM.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None


def _to_domain(row: StrategyORM) -> Strategy:
    return Strategy(
        id=row.id,
        prediction_id=row.prediction_id,
        market_id=row.market_id,
        action=_cast_action(row.action),
        side=_cast_side(row.side),
        position_size=row.position_size,
        entry_price=row.entry_price,
        take_profit=row.take_profit,
        stop_loss=row.stop_loss,
        kelly_fraction=row.kelly_fraction,
        edge=row.edge,
        skip_reason=row.skip_reason or "",
        status=_cast_status(row.status),
        executed_at=row.executed_at,
        created_at=row.created_at,
    )


def _cast_action(value: str) -> StrategyAction:
    if value not in ("buy_yes", "buy_no", "skip"):
        raise ValueError(f"unexpected action: {value}")
    return value  # type: ignore[return-value]


def _cast_side(value: str | None) -> StrategySide | None:
    if value is None:
        return None
    if value not in ("yes", "no"):
        raise ValueError(f"unexpected side: {value}")
    return value  # type: ignore[return-value]


def _cast_status(value: str) -> StrategyStatus:
    if value not in ("skipped", "pending", "executing", "active", "closed", "failed"):
        raise ValueError(f"unexpected status: {value}")
    return value  # type: ignore[return-value]
