"""Integration tests for /api/v1/strategies + full pipeline E2E."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone
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
    get_strategy_generator,
    get_strategy_repo,
)
from app.config import Settings, get_settings
from app.domain.binance import Kline, Ticker24h
from app.domain.markets import GammaEvent, GammaMarket
from app.main import app
from app.models.base import Base
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.repositories.strategy_repository_sa import SqlAlchemyStrategyRepository
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import DataAggregator
from app.services.market_scanner import MarketScanner
from app.services.strategy_generator import StrategyGenerator
from tests.fakes.fake_binance import FakeBinanceClient
from tests.fakes.fake_openai import FakeOpenAIClient
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient
from tests.fakes.fake_sentiment import FakeFearGreedClient, FakeNewsClient

ADMIN_KEY = "test-admin-key"
SCAN_AT = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
TARGET_DATE = SCAN_AT.date() + timedelta(days=2)


def _clock() -> datetime:
    return SCAN_AT


def _buy_no_response() -> dict:
    """Canned AI response with edge = 0.25 - 0.55 = -0.30 and confidence 0.78."""
    return {
        "predicted_probability": 0.25,
        "confidence": 0.78,
        "direction": "bearish",
        "key_factors": ["ETF outflows", "RSI oversold"],
        "risk_factors": ["FOMC", "Short squeeze"],
        "technical_analysis": "RSI 38, MACD bearish.",
        "sentiment_analysis": "F&G 38 Fear.",
        "news_impact": "ETF outflows $150M.",
        "onchain_analysis": "Exchange inflows $240M.",
        "reasoning": "BTC below threshold with insufficient time; strong bearish.",
        "recommended_action": "buy_no",
    }


def _skip_response() -> dict:
    """Response with abs(edge) = 0.05 → below 25% floor, AI correctly says skip."""
    return {
        "predicted_probability": 0.50,
        "confidence": 0.80,
        "direction": "neutral",
        "key_factors": ["Balanced tech", "Neutral sentiment"],
        "risk_factors": ["Low conviction", "No clear catalyst"],
        "technical_analysis": "Indicators mixed.",
        "sentiment_analysis": "F&G neutral.",
        "news_impact": "No significant news.",
        "onchain_analysis": "Normal flows.",
        "reasoning": "Edge too small to trade.",
        "recommended_action": "skip",
    }


def _klines(count: int = 24 * 7) -> list[Kline]:
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
def fake_gamma() -> FakePolymarketGammaClient:
    return FakePolymarketGammaClient(
        events=[GammaEvent(id="evt-1", slug="btc", title="Bitcoin above 66000 on April 7", active=True)],
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
    )


def _make_client(session_factory, fake_gamma, canned_ai: dict) -> Iterator[TestClient]:
    fake_binance = FakeBinanceClient(
        klines={
            ("BTCUSDT", "1h"): _klines(24 * 7),
            ("BTCUSDT", "1d"): _klines(30),
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
    )
    fake_fng = FakeFearGreedClient()
    fake_news = FakeNewsClient()
    fake_openai = FakeOpenAIClient(response=canned_ai)

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    async def _scanner(session: AsyncSession = Depends(_get_session)) -> MarketScanner:
        return MarketScanner(
            gamma=fake_gamma, repo=SqlAlchemyMarketRepository(session), clock=_clock,
        )

    async def _aggregator() -> DataAggregator:
        return DataAggregator(binance=fake_binance, fear_greed=fake_fng, news=fake_news)

    async def _predictor(session: AsyncSession = Depends(_get_session)) -> AIPredictor:
        return AIPredictor(openai=fake_openai, repo=SqlAlchemyPredictionRepository(session))

    def _gen() -> StrategyGenerator:
        return StrategyGenerator(vault_balance=Decimal("100000"))

    def _settings() -> Settings:
        return Settings(admin_api_key=ADMIN_KEY)

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_gamma_client] = lambda: fake_gamma
    app.dependency_overrides[get_binance_client] = lambda: fake_binance
    app.dependency_overrides[get_fear_greed_client] = lambda: fake_fng
    app.dependency_overrides[get_news_client] = lambda: fake_news
    app.dependency_overrides[get_openai_client] = lambda: fake_openai
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_market_scanner] = _scanner
    app.dependency_overrides[get_data_aggregator] = _aggregator
    app.dependency_overrides[get_ai_predictor] = _predictor
    app.dependency_overrides[get_strategy_generator] = _gen
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client_buy_no(session_factory, fake_gamma):
    yield from _make_client(session_factory, fake_gamma, _buy_no_response())


@pytest.fixture
def client_skip(session_factory, fake_gamma):
    yield from _make_client(session_factory, fake_gamma, _skip_response())


def _run_full_pipeline(client: TestClient) -> dict:
    scan = client.post("/api/v1/markets/scan", headers={"Authorization": f"Bearer {ADMIN_KEY}"})
    assert scan.status_code == 200, scan.text
    trig = client.post("/api/v1/predictions/trigger", headers={"Authorization": f"Bearer {ADMIN_KEY}"})
    assert trig.status_code == 200, trig.text
    gen = client.post("/api/v1/strategies/generate", headers={"Authorization": f"Bearer {ADMIN_KEY}"})
    assert gen.status_code == 200, gen.text
    return gen.json()


class TestStrategiesEndpoints:
    def test_active_history_empty_initially(self, client_buy_no: TestClient) -> None:
        assert client_buy_no.get("/api/v1/strategies/active").json() == []
        assert client_buy_no.get("/api/v1/strategies/history").json() == []

    def test_generate_requires_admin(self, client_buy_no: TestClient) -> None:
        response = client_buy_no.post("/api/v1/strategies/generate")
        assert response.status_code == 401

    def test_generate_fails_before_prediction(self, client_buy_no: TestClient) -> None:
        response = client_buy_no.post(
            "/api/v1/strategies/generate", headers={"Authorization": f"Bearer {ADMIN_KEY}"}
        )
        assert response.status_code == 409

    def test_full_pipeline_produces_buy_no_strategy(self, client_buy_no: TestClient) -> None:
        body = _run_full_pipeline(client_buy_no)

        assert body["action"] == "buy_no"
        assert body["side"] == "no"
        assert body["status"] == "pending"
        # sqlite stores Numeric as REAL — compare with tolerance (exact on Postgres).
        assert abs(Decimal(body["entry_price"]) - Decimal("0.45")) < Decimal("0.001")
        # |edge| = 0.30, TP = 0.45 + 0.30*0.7 = 0.66, SL = 0.45 - 0.30*0.5 = 0.30
        assert abs(Decimal(body["take_profit"]) - Decimal("0.66")) < Decimal("0.001")
        assert abs(Decimal(body["stop_loss"]) - Decimal("0.30")) < Decimal("0.001")
        assert Decimal(body["position_size"]) > 0

    def test_skip_strategy_persisted_with_reason(self, client_skip: TestClient) -> None:
        body = _run_full_pipeline(client_skip)
        assert body["action"] == "skip"
        assert body["status"] == "skipped"
        assert body["skip_reason"]
        assert Decimal(body["position_size"]) == 0

    def test_active_listing_excludes_skipped(self, client_skip: TestClient) -> None:
        _run_full_pipeline(client_skip)

        active = client_skip.get("/api/v1/strategies/active").json()
        history = client_skip.get("/api/v1/strategies/history").json()
        assert len(active) == 0  # skipped is not active
        assert len(history) == 1

    def test_active_listing_includes_pending(self, client_buy_no: TestClient) -> None:
        body = _run_full_pipeline(client_buy_no)

        active = client_buy_no.get("/api/v1/strategies/active").json()
        assert len(active) == 1
        assert active[0]["id"] == body["id"]
