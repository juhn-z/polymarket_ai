"""/api/v1/system routes — status + pause/resume."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.auth import require_admin
from app.schemas.stats import SystemStatusResponse
from app.services.vault_service import VaultService

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def status(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SystemStatusResponse:
    svc = VaultService(session=session, vault=None)
    paused = await svc.is_paused()
    scheduler = getattr(request.app.state, "scheduler", None)
    monitor_task = getattr(request.app.state, "monitor_task", None)
    return SystemStatusResponse(
        paused=paused,
        scheduler_running=bool(scheduler and getattr(scheduler, "running", False)),
        monitor_running=bool(monitor_task and not monitor_task.done()),
    )


@router.post("/pause", status_code=204, dependencies=[Depends(require_admin)])
async def pause(session: AsyncSession = Depends(get_session)) -> None:
    svc = VaultService(session=session, vault=None)
    await svc.pause()


@router.post("/resume", status_code=204, dependencies=[Depends(require_admin)])
async def resume(session: AsyncSession = Depends(get_session)) -> None:
    svc = VaultService(session=session, vault=None)
    await svc.resume()
