"""SQLAlchemy implementation of MarketRepository."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.markets import Market, MarketResolution, MarketStatus
from app.models.market import MarketORM


class SqlAlchemyMarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, market: Market) -> Market:
        if market.id is None:
            row = MarketORM(
                polymarket_condition_id=market.polymarket_condition_id,
                polymarket_token_id=market.polymarket_token_id,
                event_slug=market.event_slug,
                question=market.question,
                price_threshold=market.price_threshold,
                target_date=market.target_date,
                current_yes_price=market.current_yes_price,
                current_no_price=market.current_no_price,
                selected_at=market.selected_at,
                status=market.status,
                resolution=market.resolution,
            )
            self._session.add(row)
            await self._session.flush()
            return _to_domain(row)

        row = await self._session.get(MarketORM, market.id)
        if row is None:
            raise ValueError(f"Market id={market.id} not found")
        row.current_yes_price = market.current_yes_price
        row.current_no_price = market.current_no_price
        row.status = market.status
        row.resolution = market.resolution
        await self._session.flush()
        return _to_domain(row)

    async def get_by_condition_id(self, condition_id: str) -> Market | None:
        stmt = select(MarketORM).where(MarketORM.polymarket_condition_id == condition_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_latest_for_date(self, target: date) -> Market | None:
        stmt = (
            select(MarketORM)
            .where(MarketORM.target_date == target)
            .order_by(MarketORM.selected_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_latest(self) -> Market | None:
        stmt = select(MarketORM).order_by(MarketORM.selected_at.desc()).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_all(self) -> list[Market]:
        stmt = select(MarketORM).order_by(MarketORM.selected_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


def _to_domain(row: MarketORM) -> Market:
    return Market(
        id=row.id,
        polymarket_condition_id=row.polymarket_condition_id,
        polymarket_token_id=row.polymarket_token_id,
        event_slug=row.event_slug,
        question=row.question,
        price_threshold=row.price_threshold,
        target_date=row.target_date,
        current_yes_price=row.current_yes_price,
        current_no_price=row.current_no_price,
        selected_at=row.selected_at,
        status=_cast_status(row.status),
        resolution=_cast_resolution(row.resolution),
    )


def _cast_status(value: str) -> MarketStatus:
    if value not in ("active", "resolved", "expired"):
        raise ValueError(f"unexpected status: {value}")
    return value  # type: ignore[return-value]


def _cast_resolution(value: str | None) -> MarketResolution | None:
    if value is None:
        return None
    if value not in ("yes", "no"):
        raise ValueError(f"unexpected resolution: {value}")
    return value  # type: ignore[return-value]
