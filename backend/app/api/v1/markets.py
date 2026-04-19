"""/api/v1/markets routes."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_market_repo, get_market_scanner
from app.auth import require_admin
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.schemas.market import MarketResponse
from app.services.market_scanner import MarketScanner

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/today", response_model=MarketResponse)
async def get_today(
    repo: SqlAlchemyMarketRepository = Depends(get_market_repo),
) -> MarketResponse:
    market = await repo.get_latest()
    if market is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No market selected yet",
        )
    return MarketResponse.from_domain(market)


@router.post("/scan", response_model=MarketResponse, dependencies=[Depends(require_admin)])
async def scan(
    scanner: MarketScanner = Depends(get_market_scanner),
) -> MarketResponse:
    chosen = await scanner.scan_today()
    if chosen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eligible Polymarket BTC market found",
        )
    return MarketResponse.from_domain(chosen)
