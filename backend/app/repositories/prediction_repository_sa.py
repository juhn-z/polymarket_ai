"""SQLAlchemy implementation of PredictionRepository."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.predictions import Prediction, PredictionDirection, PredictionRecommendation
from app.models.prediction import PredictionORM


class SqlAlchemyPredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, prediction: Prediction) -> Prediction:
        if prediction.id is None:
            row = PredictionORM(
                market_id=prediction.market_id,
                predicted_probability=prediction.predicted_probability,
                confidence=prediction.confidence,
                direction=prediction.direction,
                key_factors=list(prediction.key_factors),
                risk_factors=list(prediction.risk_factors),
                technical_analysis=prediction.technical_analysis,
                sentiment_analysis=prediction.sentiment_analysis,
                news_impact=prediction.news_impact,
                onchain_analysis=prediction.onchain_analysis,
                reasoning=prediction.reasoning,
                recommended_action=prediction.recommended_action,
                market_probability=prediction.market_probability,
                edge=prediction.edge,
                model_version=prediction.model_version,
                prompt_version=prediction.prompt_version,
                seed=prediction.seed,
                raw_request=prediction.raw_request,
                raw_response=prediction.raw_response,
                data_snapshot=prediction.data_snapshot,
                tokens_used=prediction.tokens_used,
                latency_ms=prediction.latency_ms,
            )
            self._session.add(row)
            await self._session.flush()
            return _to_domain(row)

        row = await self._session.get(PredictionORM, prediction.id)
        if row is None:
            raise ValueError(f"Prediction id={prediction.id} not found")
        return _to_domain(row)

    async def get_by_id(self, prediction_id: int) -> Prediction | None:
        row = await self._session.get(PredictionORM, prediction_id)
        return _to_domain(row) if row else None

    async def get_latest_for_market(self, market_id: int) -> Prediction | None:
        stmt = (
            select(PredictionORM)
            .where(PredictionORM.market_id == market_id)
            .order_by(PredictionORM.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_latest(self) -> Prediction | None:
        stmt = select(PredictionORM).order_by(PredictionORM.created_at.desc()).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def list_all(self) -> list[Prediction]:
        stmt = select(PredictionORM).order_by(PredictionORM.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]


def _to_domain(row: PredictionORM) -> Prediction:
    return Prediction(
        id=row.id,
        market_id=row.market_id,
        predicted_probability=row.predicted_probability,
        confidence=row.confidence,
        direction=_cast_direction(row.direction),
        key_factors=list(row.key_factors or []),
        risk_factors=list(row.risk_factors or []),
        technical_analysis=row.technical_analysis,
        sentiment_analysis=row.sentiment_analysis,
        news_impact=row.news_impact,
        onchain_analysis=row.onchain_analysis,
        reasoning=row.reasoning,
        recommended_action=_cast_action(row.recommended_action),
        market_probability=row.market_probability,
        edge=row.edge,
        model_version=row.model_version,
        prompt_version=row.prompt_version,
        seed=row.seed,
        raw_request=dict(row.raw_request or {}),
        raw_response=dict(row.raw_response or {}),
        data_snapshot=dict(row.data_snapshot or {}),
        tokens_used=row.tokens_used,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
    )


def _cast_direction(value: str) -> PredictionDirection:
    if value not in ("bullish", "bearish", "neutral"):
        raise ValueError(f"unexpected direction: {value}")
    return value  # type: ignore[return-value]


def _cast_action(value: str) -> PredictionRecommendation:
    if value not in ("buy_yes", "buy_no", "skip"):
        raise ValueError(f"unexpected recommended_action: {value}")
    return value  # type: ignore[return-value]
