"""FastAPI dependency providers (DI)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.protocols import PolymarketGammaClient
from app.config import Settings, get_settings
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.services.market_scanner import MarketScanner


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_gamma_client(request: Request) -> PolymarketGammaClient:
    return request.app.state.gamma_client


def get_market_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAlchemyMarketRepository:
    return SqlAlchemyMarketRepository(session)


def get_market_scanner(
    gamma: PolymarketGammaClient = Depends(get_gamma_client),
    repo: SqlAlchemyMarketRepository = Depends(get_market_repo),
) -> MarketScanner:
    return MarketScanner(gamma=gamma, repo=repo)


__all__ = [
    "get_session",
    "get_gamma_client",
    "get_market_repo",
    "get_market_scanner",
    "get_settings",
]
