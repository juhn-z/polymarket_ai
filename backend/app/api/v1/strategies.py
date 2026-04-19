"""/api/v1/strategies routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_market_repo,
    get_prediction_repo,
    get_strategy_generator,
    get_strategy_repo,
)
from app.auth import require_admin
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.repositories.strategy_repository_sa import SqlAlchemyStrategyRepository
from app.schemas.strategy import StrategyResponse
from app.services.strategy_generator import StrategyGenerator

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("/active", response_model=list[StrategyResponse])
async def list_active(
    repo: SqlAlchemyStrategyRepository = Depends(get_strategy_repo),
) -> list[StrategyResponse]:
    rows = await repo.list_active()
    return [StrategyResponse.from_domain(s) for s in rows]


@router.get("/history", response_model=list[StrategyResponse])
async def list_history(
    repo: SqlAlchemyStrategyRepository = Depends(get_strategy_repo),
) -> list[StrategyResponse]:
    rows = await repo.list_all()
    return [StrategyResponse.from_domain(s) for s in rows]


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_detail(
    strategy_id: int,
    repo: SqlAlchemyStrategyRepository = Depends(get_strategy_repo),
) -> StrategyResponse:
    s = await repo.get_by_id(strategy_id)
    if s is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )
    return StrategyResponse.from_domain(s)


@router.post("/generate", response_model=StrategyResponse, dependencies=[Depends(require_admin)])
async def generate(
    market_repo: SqlAlchemyMarketRepository = Depends(get_market_repo),
    prediction_repo: SqlAlchemyPredictionRepository = Depends(get_prediction_repo),
    strategy_repo: SqlAlchemyStrategyRepository = Depends(get_strategy_repo),
    generator: StrategyGenerator = Depends(get_strategy_generator),
) -> StrategyResponse:
    """Generate a strategy from the latest market + latest prediction.

    Returns a Strategy record (status=`pending` for trades, `skipped` for
    no-trade decisions). Actual execution happens in M5 Trade Executor.
    """
    market = await market_repo.get_latest()
    if market is None or market.id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No market selected. Run POST /api/v1/markets/scan first.",
        )
    prediction = await prediction_repo.get_latest_for_market(market.id)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No prediction for latest market. Run POST /api/v1/predictions/trigger first.",
        )

    strategy = generator.generate(prediction=prediction, market=market)
    saved = await strategy_repo.save(strategy)
    return StrategyResponse.from_domain(saved)
