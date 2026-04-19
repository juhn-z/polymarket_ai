"""Integration tests for /api/v1/markets endpoints (sqlite + FastAPI TestClient)."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.adapters.protocols import PolymarketGammaClient
from app.api.deps import get_gamma_client, get_session
from app.config import Settings, get_settings
from app.domain.markets import GammaEvent, GammaMarket, Market
from app.main import app
from app.models.base import Base
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient

ADMIN_KEY = "test-admin-key"


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
        events=[
            GammaEvent(
                id="evt-1",
                slug="bitcoin-above-april-6",
                title="Bitcoin above 66000 on April 6",
                active=True,
            ),
        ],
        markets={
            "evt-1": [
                GammaMarket(
                    condition_id="0xchosen",
                    yes_token_id="yes-0xchosen",
                    no_token_id="no-0xchosen",
                    question="Bitcoin above 66000 on April 6?",
                    price_threshold=66000,
                    target_date=date(2026, 4, 6),
                    yes_price=Decimal("0.50"),
                    no_price=Decimal("0.50"),
                    volume_24h=Decimal("12345"),
                ),
            ],
        },
    )


@pytest.fixture
def client(session_factory, fake_gamma) -> Iterator[TestClient]:
    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    def _get_gamma() -> PolymarketGammaClient:
        return fake_gamma

    def _get_settings() -> Settings:
        return Settings(admin_api_key=ADMIN_KEY)

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_gamma_client] = _get_gamma
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


class TestMarketsEndpoints:
    def test_get_today_returns_404_when_no_market_selected(self, client: TestClient) -> None:
        response = client.get("/api/v1/markets/today")
        assert response.status_code == 404

    def test_post_scan_requires_admin_auth(self, client: TestClient) -> None:
        response = client.post("/api/v1/markets/scan")
        assert response.status_code == 401

    def test_post_scan_rejects_wrong_token(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/markets/scan",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert response.status_code == 401

    def test_post_scan_persists_chosen_market(
        self, client: TestClient, fake_gamma: FakePolymarketGammaClient,
    ) -> None:
        response = client.post(
            "/api/v1/markets/scan",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["polymarket_condition_id"] == "0xchosen"
        assert body["price_threshold"] == 66000
        assert body["status"] == "active"
        assert "id" in body
        # gamma client should have been called once for events + once for markets
        assert fake_gamma.search_calls == ["bitcoin"]
        assert fake_gamma.market_calls == ["evt-1"]

    def test_get_today_returns_latest_after_scan(self, client: TestClient) -> None:
        scan = client.post(
            "/api/v1/markets/scan",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        )
        assert scan.status_code == 200

        today_resp = client.get("/api/v1/markets/today")
        assert today_resp.status_code == 200
        assert today_resp.json()["polymarket_condition_id"] == "0xchosen"

    async def test_repository_round_trip(self, session_factory) -> None:
        async with session_factory() as session:
            repo = SqlAlchemyMarketRepository(session)
            saved = await repo.save(
                Market(
                    polymarket_condition_id="0xrt",
                    polymarket_token_id="yes-rt",
                    event_slug="rt",
                    question="Bitcoin above 1?",
                    price_threshold=1,
                    target_date=date(2026, 4, 19),
                    current_yes_price=Decimal("0.5"),
                    current_no_price=Decimal("0.5"),
                    selected_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
                ),
            )
            await session.commit()
            assert saved.id is not None

            fetched = await repo.get_by_condition_id("0xrt")
            assert fetched is not None
            assert fetched.id == saved.id
            assert fetched.question == "Bitcoin above 1?"
