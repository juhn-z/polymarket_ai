"""/api/v1/predictions routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_ai_predictor,
    get_data_aggregator,
    get_market_repo,
    get_prediction_repo,
)
from app.auth import require_admin
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.schemas.prediction import PredictionDetailResponse, PredictionResponse
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import DataAggregator

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/today", response_model=PredictionResponse)
async def get_today(
    repo: SqlAlchemyPredictionRepository = Depends(get_prediction_repo),
) -> PredictionResponse:
    latest = await repo.get_latest()
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prediction generated yet",
        )
    return PredictionResponse.from_domain(latest)


@router.get("/history", response_model=list[PredictionResponse])
async def get_history(
    repo: SqlAlchemyPredictionRepository = Depends(get_prediction_repo),
) -> list[PredictionResponse]:
    all_preds = await repo.list_all()
    return [PredictionResponse.from_domain(p) for p in all_preds]


@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_detail(
    prediction_id: int,
    repo: SqlAlchemyPredictionRepository = Depends(get_prediction_repo),
) -> PredictionDetailResponse:
    prediction = await repo.get_by_id(prediction_id)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction {prediction_id} not found",
        )
    return PredictionDetailResponse.from_domain(prediction)


@router.post(
    "/trigger",
    response_model=PredictionResponse,
    dependencies=[Depends(require_admin)],
)
async def trigger(
    market_repo: SqlAlchemyMarketRepository = Depends(get_market_repo),
    aggregator: DataAggregator = Depends(get_data_aggregator),
    predictor: AIPredictor = Depends(get_ai_predictor),
) -> PredictionResponse:
    market = await market_repo.get_latest()
    if market is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No market selected yet — run POST /api/v1/markets/scan first",
        )
    bundle = await aggregator.collect_for(market)
    prediction = await predictor.predict(market, bundle)
    return PredictionResponse.from_domain(prediction)
