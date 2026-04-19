"""Integration tests for /api/v1/trades — full pipeline incl. execution."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import (
    get_ai_predictor,
    get_binance_client,
    get_clob_client,
    get_data_aggregator,
    get_fear_greed_client,
    get_gamma_client,
    get_market_scanner,
    get_news_client,
    get_openai_client,
    get_session,
    get_strategy_generator,
    get_trade_executor,
    get_vault_client,
)
from app.config import Settings, get_settings
from app.domain.binance import Kline, Ticker24h
from app.domain.markets import GammaEvent, GammaMarket
from app.main import app
from app.models.base import Base
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.repositories.strategy_repository_sa import SqlAlchemyStrategyRepository
from app.repositories.trade_repository_sa import SqlAlchemyTradeRepository
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import DataAggregator
from app.services.market_scanner import MarketScanner
from app.services.strategy_generator import StrategyGenerator
from app.services.trade_executor import TradeExecutor
from tests.fakes.fake_binance import FakeBinanceClient
from tests.fakes.fake_openai import FakeOpenAIClient
from tests.fakes.fake_polymarket_clob import FakePolymarketCLOBClient
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient
from tests.fakes.fake_sentiment import FakeFearGreedClient, FakeNewsClient
from tests.fakes.fake_vault import FakeVaultClient

ADMIN_KEY = "test-admin-key"
SCAN_AT = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
TARGET_DATE = SCAN_AT.date() + timedelta(days=2)


def _clock():
    return SCAN_AT


def _buy_no_response() -> dict:
    return {
        "predicted_probability": 0.25,
        "confidence": 0.78,
        "direction": "bearish",
        "key_factors": ["a", "b"],
        "risk_factors": ["c", "d"],
        "technical_analysis": "t",
        "sentiment_analysis": "s",
        "news_impact": "n",
        "onchain_analysis": "o",
        "reasoning": "r",
        "recommended_action": "buy_no",
    }


def _klines(count: int = 24 * 7):
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
def fakes():
    return {
        "gamma": FakePolymarketGammaClient(
            events=[GammaEvent(id="evt-1", slug="btc", title="Bitcoin above 66000 on April 7", active=True)],
            markets={
                "evt-1": [
                    GammaMarket(
                        condition_id="0xabc",
                        yes_token_id="yes-abc",
                        no_token_id="no-abc",
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
            klines={("BTCUSDT", "1h"): _klines(), ("BTCUSDT", "1d"): _klines(30)},
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
        "fng": FakeFearGreedClient(),
        "news": FakeNewsClient(),
        "openai": FakeOpenAIClient(response=_buy_no_response()),
        "clob": FakePolymarketCLOBClient(prices={"no-abc": Decimal("0.45")}),
        "vault": FakeVaultClient(available_balance=Decimal("100000")),
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

    async def _scanner(session: AsyncSession = Depends(_get_session)) -> MarketScanner:
        return MarketScanner(gamma=fakes["gamma"], repo=SqlAlchemyMarketRepository(session), clock=_clock)

    async def _aggregator() -> DataAggregator:
        return DataAggregator(binance=fakes["binance"], fear_greed=fakes["fng"], news=fakes["news"])

    async def _predictor(session: AsyncSession = Depends(_get_session)) -> AIPredictor:
        return AIPredictor(openai=fakes["openai"], repo=SqlAlchemyPredictionRepository(session))

    async def _executor(session: AsyncSession = Depends(_get_session)) -> TradeExecutor:
        return TradeExecutor(
            clob=fakes["clob"],
            vault=fakes["vault"],
            strategy_repo=SqlAlchemyStrategyRepository(session),
            trade_repo=SqlAlchemyTradeRepository(session),
        )

    def _gen() -> StrategyGenerator:
        return StrategyGenerator(vault_balance=Decimal("100000"))

    def _settings() -> Settings:
        return Settings(admin_api_key=ADMIN_KEY)

    overrides = {
        get_session: _get_session,
        get_gamma_client: lambda: fakes["gamma"],
        get_binance_client: lambda: fakes["binance"],
        get_fear_greed_client: lambda: fakes["fng"],
        get_news_client: lambda: fakes["news"],
        get_openai_client: lambda: fakes["openai"],
        get_clob_client: lambda: fakes["clob"],
        get_vault_client: lambda: fakes["vault"],
        get_settings: _settings,
        get_market_scanner: _scanner,
        get_data_aggregator: _aggregator,
        get_ai_predictor: _predictor,
        get_strategy_generator: _gen,
        get_trade_executor: _executor,
    }
    for k, v in overrides.items():
        app.dependency_overrides[k] = v
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


class TestTradesEndpoints:
    def test_empty_lists_initially(self, client: TestClient) -> None:
        assert client.get("/api/v1/trades/active").json() == []
        assert client.get("/api/v1/trades/history").json() == []

    def test_execute_requires_admin(self, client: TestClient) -> None:
        response = client.post("/api/v1/trades/execute")
        assert response.status_code == 401

    def test_full_pipeline_yields_filled_trade(self, client: TestClient, fakes) -> None:
        # scan → predict → generate → execute
        assert client.post("/api/v1/markets/scan", headers=_auth()).status_code == 200
        assert client.post("/api/v1/predictions/trigger", headers=_auth()).status_code == 200
        assert client.post("/api/v1/strategies/generate", headers=_auth()).status_code == 200

        resp = client.post("/api/v1/trades/execute", headers=_auth())
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["status"] == "filled"
        assert body["side"] == "no"
        assert body["action"] == "buy"

        # Vault was tapped, CLOB was called.
        assert len(fakes["vault"].withdraw_calls) == 1
        assert fakes["clob"].place_calls[0]["side"] == "buy"

        # History shows the trade.
        history = client.get("/api/v1/trades/history").json()
        assert len(history) == 1
        assert history[0]["id"] == body["id"]
