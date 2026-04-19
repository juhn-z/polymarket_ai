"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.polymarket_gamma import PolymarketGammaHttpClient
from app.api.v1 import markets as markets_router
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings)
    async with engine.begin() as conn:
        # M0: create tables directly. M8 swaps to alembic-managed migrations.
        await conn.run_sync(Base.metadata.create_all)
    gamma = PolymarketGammaHttpClient(base_url=settings.polymarket_gamma_api_url)

    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.gamma_client = gamma
    try:
        yield
    finally:
        await gamma.aclose()
        await engine.dispose()


app = FastAPI(title="PolyPredict AI Backend", lifespan=lifespan)
app.include_router(markets_router.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
