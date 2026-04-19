"""/api/v1/trades routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_market_repo,
    get_strategy_repo,
    get_trade_executor,
    get_trade_repo,
)
from app.auth import require_admin
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.strategy_repository_sa import SqlAlchemyStrategyRepository
from app.repositories.trade_repository_sa import SqlAlchemyTradeRepository
from app.schemas.trade import TradeResponse
from app.services.trade_executor import TradeExecutor

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/active", response_model=list[TradeResponse])
async def list_active(
    repo: SqlAlchemyTradeRepository = Depends(get_trade_repo),
) -> list[TradeResponse]:
    return [TradeResponse.from_domain(t) for t in await repo.list_active()]


@router.get("/history", response_model=list[TradeResponse])
async def list_history(
    repo: SqlAlchemyTradeRepository = Depends(get_trade_repo),
) -> list[TradeResponse]:
    return [TradeResponse.from_domain(t) for t in await repo.list_all()]


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_detail(
    trade_id: int,
    repo: SqlAlchemyTradeRepository = Depends(get_trade_repo),
) -> TradeResponse:
    t = await repo.get_by_id(trade_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade {trade_id} not found",
        )
    return TradeResponse.from_domain(t)


@router.post("/execute", response_model=TradeResponse, dependencies=[Depends(require_admin)])
async def execute(
    market_repo: SqlAlchemyMarketRepository = Depends(get_market_repo),
    strategy_repo: SqlAlchemyStrategyRepository = Depends(get_strategy_repo),
    executor: TradeExecutor = Depends(get_trade_executor),
) -> TradeResponse:
    """Execute the latest pending strategy for the latest market."""
    market = await market_repo.get_latest()
    if market is None or market.id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No market selected")
    strategy = await strategy_repo.get_latest_for_market(market.id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No strategy for latest market")
    if strategy.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Strategy id={strategy.id} has status={strategy.status}; expected 'pending'",
        )
    trade = await executor.execute(strategy=strategy, market=market)
    return TradeResponse.from_domain(trade)
