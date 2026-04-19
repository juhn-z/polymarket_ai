"""Prediction ORM round-trip test against sqlite (StaticPool)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.domain.markets import Market
from app.domain.predictions import Prediction
from app.models.base import Base
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_prediction_round_trip(session_factory) -> None:
    async with session_factory() as session:
        # Parent market first (FK constraint).
        market_repo = SqlAlchemyMarketRepository(session)
        saved_market = await market_repo.save(
            Market(
                polymarket_condition_id="0xabc",
                polymarket_token_id="yes-token",
                event_slug="bitcoin-above",
                question="Bitcoin above 66000 on April 7?",
                price_threshold=66000,
                scan_date=date(2026, 4, 5),
                target_date=date(2026, 4, 7),
                current_yes_price=Decimal("0.55"),
                current_no_price=Decimal("0.45"),
                selected_at=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
            )
        )
        await session.commit()
        assert saved_market.id is not None

    async with session_factory() as session:
        repo = SqlAlchemyPredictionRepository(session)
        saved = await repo.save(
            Prediction(
                market_id=saved_market.id,
                predicted_probability=Decimal("0.25"),
                confidence=Decimal("0.78"),
                direction="bearish",
                key_factors=["factor a", "factor b"],
                risk_factors=["risk a", "risk b"],
                technical_analysis="RSI low",
                sentiment_analysis="F&G fear",
                news_impact="ETF outflows",
                onchain_analysis="Distribution",
                reasoning="Detailed...",
                recommended_action="buy_no",
                market_probability=Decimal("0.55"),
                edge=Decimal("-0.30"),
                model_version="gpt-5.4",
                prompt_version="v1.0",
                seed=42,
                raw_request={"system": "...", "user": "..."},
                raw_response={"predicted_probability": 0.25},
                data_snapshot={"btc_current_price": "63500"},
                tokens_used=1234,
                latency_ms=987,
            )
        )
        await session.commit()
        assert saved.id is not None

    async with session_factory() as session:
        repo = SqlAlchemyPredictionRepository(session)
        fetched = await repo.get_by_id(saved.id)  # type: ignore[arg-type]
        assert fetched is not None
        assert fetched.market_id == saved_market.id
        assert fetched.predicted_probability == Decimal("0.25")
        assert fetched.direction == "bearish"
        assert fetched.key_factors == ["factor a", "factor b"]
        assert fetched.raw_response == {"predicted_probability": 0.25}
        # sqlite stores Numeric as REAL — compare with tolerance rather than exact Decimal.
        # On Postgres this round-trips exactly.
        assert abs(fetched.edge - Decimal("-0.30")) < Decimal("0.000001")

        latest = await repo.get_latest_for_market(saved_market.id)  # type: ignore[arg-type]
        assert latest is not None
        assert latest.id == fetched.id
