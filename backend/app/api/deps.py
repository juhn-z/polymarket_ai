"""FastAPI dependency providers (DI)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.protocols import (
    BinanceClient,
    FearGreedClient,
    NewsClient,
    OpenAIClient,
    PolymarketGammaClient,
)
from app.config import Settings, get_settings
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.repositories.strategy_repository_sa import SqlAlchemyStrategyRepository
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import DataAggregator
from app.services.market_scanner import MarketScanner
from app.services.strategy_generator import StrategyGenerator


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


def get_binance_client(request: Request) -> BinanceClient:
    return request.app.state.binance_client


def get_fear_greed_client(request: Request) -> FearGreedClient:
    return request.app.state.fear_greed_client


def get_news_client(request: Request) -> NewsClient:
    return request.app.state.news_client


def get_openai_client(request: Request) -> OpenAIClient:
    return request.app.state.openai_client


def get_market_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAlchemyMarketRepository:
    return SqlAlchemyMarketRepository(session)


def get_prediction_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAlchemyPredictionRepository:
    return SqlAlchemyPredictionRepository(session)


def get_strategy_repo(
    session: AsyncSession = Depends(get_session),
) -> SqlAlchemyStrategyRepository:
    return SqlAlchemyStrategyRepository(session)


def get_strategy_generator(
    settings: Settings = Depends(get_settings),
) -> StrategyGenerator:
    # NOTE: vault balance is mocked to a sensible default until the VaultClient
    # adapter lands in M5. Until then, StrategyGenerator uses a static balance
    # for sizing math — the Trade Executor will pull the live balance when it
    # actually withdraws from the vault.
    from decimal import Decimal
    return StrategyGenerator(vault_balance=Decimal("100000"))


def get_market_scanner(
    gamma: PolymarketGammaClient = Depends(get_gamma_client),
    repo: SqlAlchemyMarketRepository = Depends(get_market_repo),
) -> MarketScanner:
    return MarketScanner(gamma=gamma, repo=repo)


def get_data_aggregator(
    binance: BinanceClient = Depends(get_binance_client),
    fear_greed: FearGreedClient = Depends(get_fear_greed_client),
    news: NewsClient = Depends(get_news_client),
) -> DataAggregator:
    return DataAggregator(binance=binance, fear_greed=fear_greed, news=news)


def get_ai_predictor(
    openai: OpenAIClient = Depends(get_openai_client),
    repo: SqlAlchemyPredictionRepository = Depends(get_prediction_repo),
) -> AIPredictor:
    return AIPredictor(openai=openai, repo=repo)


__all__ = [
    "get_session",
    "get_gamma_client",
    "get_binance_client",
    "get_fear_greed_client",
    "get_news_client",
    "get_openai_client",
    "get_market_repo",
    "get_prediction_repo",
    "get_strategy_repo",
    "get_market_scanner",
    "get_data_aggregator",
    "get_ai_predictor",
    "get_strategy_generator",
    "get_settings",
]
