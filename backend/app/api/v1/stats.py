"""/api/v1/stats routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_session, get_vault_client
from app.schemas.stats import (
    DailyPnLResponse,
    LeaderboardEntryResponse,
    OverviewResponse,
    VaultSnapshotResponse,
)
from app.services.vault_service import VaultService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/stats", tags=["stats"])


def _service(session: AsyncSession, vault) -> VaultService:
    return VaultService(session=session, vault=vault)


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    session: AsyncSession = Depends(get_session),
    vault=Depends(get_vault_client),
) -> OverviewResponse:
    stats = await _service(session, _safe_vault(vault)).overview()
    return OverviewResponse(
        tvl=stats.tvl,
        share_price=stats.share_price,
        total_pnl=stats.total_pnl,
        total_trades=stats.total_trades,
        win_rate=stats.win_rate,
        active_positions=stats.active_positions,
    )


@router.get("/daily", response_model=list[DailyPnLResponse])
async def daily(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> list[DailyPnLResponse]:
    svc = VaultService(session=session, vault=None)
    rows = await svc.daily_pnl(days=days)
    return [DailyPnLResponse(day=r.day, pnl=r.pnl, trade_count=r.trade_count) for r in rows]


@router.get("/vault", response_model=list[VaultSnapshotResponse])
async def vault_history(
    limit: int = Query(168, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> list[VaultSnapshotResponse]:
    svc = VaultService(session=session, vault=None)
    rows = await svc.list_snapshots(limit=limit)
    return [
        VaultSnapshotResponse(
            id=r.id or 0,
            total_assets=r.total_assets,
            share_price=r.share_price,
            tvl=r.tvl,
            depositor_count=r.depositor_count,
            deployed_amount=r.deployed_amount,
            snapshot_at=r.snapshot_at,
        )
        for r in rows
    ]


@router.get("/leaderboard", response_model=list[LeaderboardEntryResponse])
async def leaderboard() -> list[LeaderboardEntryResponse]:
    # Leaderboard requires on-chain deposit event indexing, deferred to a
    # follow-up milestone. Return empty list so the endpoint is stable.
    return []


def _safe_vault(vault):
    """Return ``None`` if the vault client is the unconfigured sentinel."""
    try:
        # The real VaultChainClient has these methods; the sentinel raises.
        return vault if hasattr(vault, "total_assets") else None
    except Exception:  # pragma: no cover
        return None
