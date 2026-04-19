"""VaultService — stats + periodic snapshots + pause flag."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.protocols import VaultClient
from app.domain.stats import DailyPnL, OverviewStats, VaultSnapshot
from app.models.system_log import SystemLogORM
from app.models.trade import TradeORM
from app.models.vault_snapshot import VaultSnapshotORM

PAUSE_FLAG_SOURCE = "system.pause"
PAUSE_FLAG_MESSAGE = "paused"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VaultService:
    def __init__(
        self,
        session: AsyncSession,
        vault: VaultClient | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._session = session
        self._vault = vault
        self._clock = clock

    # ------------------------------------------------------------------ Snapshots

    async def snapshot(self) -> VaultSnapshot:
        if self._vault is None:
            raise RuntimeError("VaultService needs a VaultClient to snapshot")
        total = await self._vault.total_assets()
        share = await self._vault.share_price()
        available = await self._vault.available_balance()
        deployed = total - available

        row = VaultSnapshotORM(
            total_assets=total,
            share_price=share,
            tvl=total,
            depositor_count=0,
            deployed_amount=deployed,
            snapshot_at=self._clock(),
        )
        self._session.add(row)
        await self._session.flush()
        return _snapshot_to_domain(row)

    async def list_snapshots(self, limit: int = 168) -> list[VaultSnapshot]:
        stmt = (
            select(VaultSnapshotORM)
            .order_by(VaultSnapshotORM.snapshot_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_snapshot_to_domain(r) for r in rows]

    # ------------------------------------------------------------------ Aggregates

    async def overview(self) -> OverviewStats:
        tvl = await self._current_tvl()
        share_price = await self._current_share_price()

        pnl_stmt = select(func.coalesce(func.sum(TradeORM.pnl), 0)).where(
            TradeORM.action == "sell"
        )
        total_pnl = (await self._session.execute(pnl_stmt)).scalar_one() or Decimal("0")

        count_stmt = select(func.count(TradeORM.id)).where(TradeORM.action == "sell")
        total_trades = (await self._session.execute(count_stmt)).scalar_one() or 0

        win_stmt = select(func.count(TradeORM.id)).where(
            TradeORM.action == "sell",
            TradeORM.pnl.is_not(None),
            TradeORM.pnl > 0,
        )
        win_count = (await self._session.execute(win_stmt)).scalar_one() or 0
        win_rate = (
            Decimal(win_count) / Decimal(total_trades)
            if total_trades > 0 else Decimal("0")
        )

        active_stmt = select(func.count(TradeORM.id)).where(
            TradeORM.status.in_(("pending", "partial"))
        )
        active = (await self._session.execute(active_stmt)).scalar_one() or 0

        return OverviewStats(
            tvl=tvl,
            share_price=share_price,
            total_pnl=Decimal(str(total_pnl)),
            total_trades=int(total_trades),
            win_rate=win_rate,
            active_positions=int(active),
        )

    async def daily_pnl(self, days: int = 30) -> list[DailyPnL]:
        since = self._clock() - timedelta(days=days)
        stmt = (
            select(
                func.date(TradeORM.closed_at).label("day"),
                func.sum(TradeORM.pnl).label("pnl"),
                func.count(TradeORM.id).label("n"),
            )
            .where(
                TradeORM.action == "sell",
                TradeORM.closed_at.is_not(None),
                TradeORM.closed_at >= since,
            )
            .group_by(func.date(TradeORM.closed_at))
            .order_by(func.date(TradeORM.closed_at))
        )
        out: list[DailyPnL] = []
        for row in (await self._session.execute(stmt)).all():
            d = row.day
            if isinstance(d, str):  # sqlite returns str
                d = date.fromisoformat(d)
            out.append(
                DailyPnL(
                    day=d,
                    pnl=Decimal(str(row.pnl or 0)),
                    trade_count=int(row.n),
                )
            )
        return out

    async def _current_tvl(self) -> Decimal:
        if self._vault is not None:
            try:
                return await self._vault.total_assets()
            except Exception:
                pass
        # Fallback: read from latest snapshot row.
        stmt = (
            select(VaultSnapshotORM)
            .order_by(VaultSnapshotORM.snapshot_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row.tvl if row else Decimal("0")

    async def _current_share_price(self) -> Decimal:
        if self._vault is not None:
            try:
                return await self._vault.share_price()
            except Exception:
                pass
        stmt = (
            select(VaultSnapshotORM)
            .order_by(VaultSnapshotORM.snapshot_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row.share_price if row else Decimal("1")

    # ------------------------------------------------------------------ Pause

    async def is_paused(self) -> bool:
        stmt = (
            select(SystemLogORM)
            .where(
                SystemLogORM.source == PAUSE_FLAG_SOURCE,
                SystemLogORM.message == PAUSE_FLAG_MESSAGE,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def pause(self) -> None:
        if await self.is_paused():
            return
        self._session.add(
            SystemLogORM(
                level="WARN",
                source=PAUSE_FLAG_SOURCE,
                message=PAUSE_FLAG_MESSAGE,
                context={},
            )
        )
        await self._session.flush()

    async def resume(self) -> None:
        stmt = select(SystemLogORM).where(
            SystemLogORM.source == PAUSE_FLAG_SOURCE,
            SystemLogORM.message == PAUSE_FLAG_MESSAGE,
        )
        for row in (await self._session.execute(stmt)).scalars().all():
            await self._session.delete(row)
        await self._session.flush()


def _snapshot_to_domain(row: VaultSnapshotORM) -> VaultSnapshot:
    return VaultSnapshot(
        id=row.id,
        total_assets=row.total_assets,
        share_price=row.share_price,
        tvl=row.tvl,
        depositor_count=row.depositor_count,
        deployed_amount=row.deployed_amount,
        snapshot_at=row.snapshot_at,
    )
