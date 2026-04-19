"""Integration tests for /api/v1/stats and /api/v1/system."""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_session, get_vault_client
from app.config import Settings, get_settings
from app.main import app
from app.models.base import Base
from tests.fakes.fake_vault import FakeVaultClient

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
def client(session_factory) -> Iterator[TestClient]:
    fake_vault = FakeVaultClient()

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    def _settings() -> Settings:
        return Settings(admin_api_key=ADMIN_KEY)

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_vault_client] = lambda: fake_vault
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


class TestStatsAndSystem:
    def test_overview_returns_zeroed_stats_initially(self, client: TestClient) -> None:
        resp = client.get("/api/v1/stats/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert int(body["total_trades"]) == 0
        assert int(body["active_positions"]) == 0

    def test_daily_and_vault_history_are_empty_initially(self, client: TestClient) -> None:
        assert client.get("/api/v1/stats/daily").json() == []
        assert client.get("/api/v1/stats/vault").json() == []

    def test_leaderboard_placeholder(self, client: TestClient) -> None:
        assert client.get("/api/v1/stats/leaderboard").json() == []

    def test_system_pause_resume_round_trip(self, client: TestClient) -> None:
        assert client.get("/api/v1/system/status").json()["paused"] is False

        resp = client.post("/api/v1/system/pause", headers=_auth())
        assert resp.status_code == 204

        assert client.get("/api/v1/system/status").json()["paused"] is True

        resp = client.post("/api/v1/system/resume", headers=_auth())
        assert resp.status_code == 204
        assert client.get("/api/v1/system/status").json()["paused"] is False

    def test_pause_requires_admin(self, client: TestClient) -> None:
        assert client.post("/api/v1/system/pause").status_code == 401
