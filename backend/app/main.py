"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.binance import BinanceHttpClient
from app.adapters.cryptopanic import CryptoPanicHttpClient
from app.adapters.fear_greed import FearGreedHttpClient
from app.adapters.openai_client import OpenAIHttpClient
from app.adapters.polymarket_gamma import PolymarketGammaHttpClient
from app.api.v1 import markets as markets_router
from app.api.v1 import predictions as predictions_router
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Base  # side-effect: registers all ORM tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings)
    async with engine.begin() as conn:
        # M0: create tables directly. M8 swaps to alembic-managed migrations.
        await conn.run_sync(Base.metadata.create_all)

    gamma = PolymarketGammaHttpClient(base_url=settings.polymarket_gamma_api_url)
    binance = BinanceHttpClient(base_url=settings.binance_api_url)
    fear_greed = FearGreedHttpClient(base_url=settings.fear_greed_api_url)
    news = CryptoPanicHttpClient(
        base_url=settings.cryptopanic_api_url,
        api_key=settings.cryptopanic_api_key,
    )

    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.gamma_client = gamma
    app.state.binance_client = binance
    app.state.fear_greed_client = fear_greed
    app.state.news_client = news
    if settings.openai_api_key:
        app.state.openai_client = OpenAIHttpClient(api_key=settings.openai_api_key)
    else:
        # Fail clearly at call-time rather than boot-time when key is absent.
        app.state.openai_client = _UnconfiguredOpenAI()

    try:
        yield
    finally:
        await gamma.aclose()
        await binance.aclose()
        await fear_greed.aclose()
        await news.aclose()
        if isinstance(app.state.openai_client, OpenAIHttpClient):
            await app.state.openai_client.aclose()
        await engine.dispose()


class _UnconfiguredOpenAI:  # pragma: no cover - defensive runtime stub
    async def predict(self, **_kwargs):
        raise RuntimeError(
            "OpenAI client not configured. Set OPENAI_API_KEY and wire a real client in app.main.lifespan"
        )


app = FastAPI(title="PolyPredict AI Backend", lifespan=lifespan)
app.include_router(markets_router.router, prefix="/api/v1")
app.include_router(predictions_router.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
