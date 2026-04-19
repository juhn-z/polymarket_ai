"""Integration tests for /api/v1/predictions endpoints (sqlite + TestClient)."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.adapters.protocols import (
    BinanceClient,
    FearGreedClient,
    NewsClient,
    OpenAIClient,
    PolymarketGammaClient,
)
from app.api.deps import (
    get_ai_predictor,
    get_binance_client,
    get_data_aggregator,
    get_fear_greed_client,
    get_gamma_client,
    get_market_repo,
    get_market_scanner,
    get_news_client,
    get_openai_client,
    get_prediction_repo,
    get_session,
)
from app.config import Settings, get_settings
from app.domain.binance import Kline, Ticker24h
from app.domain.markets import GammaEvent, GammaMarket
from app.main import app
from app.models.base import Base
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import DataAggregator
from app.services.market_scanner import MarketScanner
from tests.fakes.fake_binance import FakeBinanceClient
from tests.fakes.fake_openai import FakeOpenAIClient
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient
from tests.fakes.fake_sentiment import FakeFearGreedClient, FakeNewsClient

ADMIN_KEY = "test-admin-key"
SCAN_AT = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
TARGET_DATE = SCAN_AT.date() + timedelta(days=2)


def _fixed_clock() -> datetime:
    return SCAN_AT


def _canned_ai_response() -> dict:
    return {
        "predicted_probability": 0.25,
        "confidence": 0.78,
        "direction": "bearish",
        "key_factors": ["factor a", "factor b"],
        "risk_factors": ["risk a", "risk b"],
        "technical_analysis": "RSI low",
        "sentiment_analysis": "F&G fear",
        "news_impact": "ETF outflows",
        "onchain_analysis": "Distribution",
        "reasoning": "Detailed reasoning goes here.",
        "recommended_action": "buy_no",
    }


def _kline_series(count: int = 24 * 7) -> list[Kline]:
    base = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
    return [
        Kline(
            open_time=base + timedelta(hours=i),
            close_time=base + timedelta(hours=i, minutes=59, seconds=59),
            open=Decimal("63000"),
            high=Decimal("63500"),
            low=Decimal("62500"),
            close=Decimal(str(63000 + i)),
            volume=Decimal("100"),
        )
        for i in range(count)
    ]


@pytest.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def fakes() -> dict:
    return {
        "gamma": FakePolymarketGammaClient(
            events=[
                GammaEvent(
                    id="evt-1",
                    slug="bitcoin-above-april-7",
                    title="Bitcoin above 66000 on April 7",
                    active=True,
                ),
            ],
            markets={
                "evt-1": [
                    GammaMarket(
                        condition_id="0xchosen",
                        yes_token_id="yes-0xchosen",
                        no_token_id="no-0xchosen",
                        question="Bitcoin above 66000 on April 7?",
                        price_threshold=66000,
                        target_date=TARGET_DATE,
                        yes_price=Decimal("0.55"),
                        no_price=Decimal("0.45"),
                        volume_24h=Decimal("50000"),
                    ),
                ],
            },
        ),
        "binance": FakeBinanceClient(
            klines={
                ("BTCUSDT", "1h"): _kline_series(24 * 7),
                ("BTCUSDT", "1d"): _kline_series(30),
            },
            tickers={
                "BTCUSDT": Ticker24h(
                    symbol="BTCUSDT",
                    last_price=Decimal("63500"),
                    high_price=Decimal("64000"),
                    low_price=Decimal("63000"),
                    volume=Decimal("12345"),
                    price_change=Decimal("-500"),
                    price_change_percent=Decimal("-0.78"),
                ),
            },
        ),
        "fear_greed": FakeFearGreedClient(),
        "news": FakeNewsClient(),
        "openai": FakeOpenAIClient(response=_canned_ai_response()),
    }


@pytest.fixture
def client(session_factory, fakes) -> Iterator[TestClient]:
    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    def _gamma() -> PolymarketGammaClient:
        return fakes["gamma"]

    def _binance() -> BinanceClient:
        return fakes["binance"]

    def _fng() -> FearGreedClient:
        return fakes["fear_greed"]

    def _news() -> NewsClient:
        return fakes["news"]

    def _openai() -> OpenAIClient:
        return fakes["openai"]

    def _settings() -> Settings:
        return Settings(admin_api_key=ADMIN_KEY)

    async def _scanner(session: AsyncSession = Depends(_get_session)) -> MarketScanner:
        return MarketScanner(
            gamma=fakes["gamma"],
            repo=SqlAlchemyMarketRepository(session),
            clock=_fixed_clock,
        )

    async def _aggregator() -> DataAggregator:
        return DataAggregator(
            binance=fakes["binance"],
            fear_greed=fakes["fear_greed"],
            news=fakes["news"],
        )

    async def _predictor(
        session: AsyncSession = Depends(_get_session),
    ) -> AIPredictor:
        return AIPredictor(
            openai=fakes["openai"],
            repo=SqlAlchemyPredictionRepository(session),
        )

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_gamma_client] = _gamma
    app.dependency_overrides[get_binance_client] = _binance
    app.dependency_overrides[get_fear_greed_client] = _fng
    app.dependency_overrides[get_news_client] = _news
    app.dependency_overrides[get_openai_client] = _openai
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_market_scanner] = _scanner
    app.dependency_overrides[get_data_aggregator] = _aggregator
    app.dependency_overrides[get_ai_predictor] = _predictor
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


class TestPredictionsEndpoints:
    def test_get_today_returns_404_before_any_prediction(self, client: TestClient) -> None:
        response = client.get("/api/v1/predictions/today")
        assert response.status_code == 404

    def test_trigger_requires_admin(self, client: TestClient) -> None:
        response = client.post("/api/v1/predictions/trigger")
        assert response.status_code == 401

    def test_trigger_fails_without_market(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/predictions/trigger",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        )
        assert response.status_code == 409
        assert "market" in response.json()["detail"].lower()

    def test_full_pipeline_scan_then_trigger_returns_prediction(
        self, client: TestClient, fakes: dict,
    ) -> None:
        scan = client.post(
            "/api/v1/markets/scan",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        )
        assert scan.status_code == 200, scan.text

        trigger = client.post(
            "/api/v1/predictions/trigger",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        )
        assert trigger.status_code == 200, trigger.text
        body = trigger.json()
        assert body["direction"] == "bearish"
        assert body["recommended_action"] == "buy_no"
        assert Decimal(body["predicted_probability"]) == Decimal("0.25")
        # edge = 0.25 - 0.55 = -0.30 (approximate on sqlite)
        assert abs(Decimal(body["edge"]) + Decimal("0.30")) < Decimal("0.000001")

        today = client.get("/api/v1/predictions/today")
        assert today.status_code == 200
        assert today.json()["id"] == body["id"]

        detail = client.get(f"/api/v1/predictions/{body['id']}")
        assert detail.status_code == 200
        detail_body = detail.json()
        assert "raw_request" in detail_body
        assert "raw_response" in detail_body
        assert "data_snapshot" in detail_body
        assert detail_body["raw_response"]["recommended_action"] == "buy_no"

        history = client.get("/api/v1/predictions/history")
        assert history.status_code == 200
        assert len(history.json()) == 1

        # Sanity: openai was called with prompt containing bundle facts.
        assert len(fakes["openai"].calls) == 1
        assert "66000" in fakes["openai"].calls[0]["user"]
