"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.binance import BinanceHttpClient
from app.adapters.cryptopanic import CryptoPanicHttpClient
from app.adapters.fear_greed import FearGreedHttpClient
from app.adapters.openai_client import OpenAIHttpClient
from app.adapters.polymarket_clob import PolymarketCLOBHttpClient
from app.adapters.polymarket_gamma import PolymarketGammaHttpClient
from app.adapters.vault_chain import VaultChainClient
from app.api.v1 import markets as markets_router
from app.api.v1 import predictions as predictions_router
from app.api.v1 import stats as stats_router
from app.api.v1 import strategies as strategies_router
from app.api.v1 import system as system_router
from app.api.v1 import trades as trades_router
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Base  # side-effect: registers all ORM tables
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository
from app.repositories.prediction_repository_sa import SqlAlchemyPredictionRepository
from app.repositories.strategy_repository_sa import SqlAlchemyStrategyRepository
from app.repositories.trade_repository_sa import SqlAlchemyTradeRepository
from app.services.ai_predictor import AIPredictor
from app.services.data_aggregator import DataAggregator
from app.services.market_scanner import MarketScanner
from app.services.position_monitor import PositionMonitor
from app.services.strategy_generator import StrategyGenerator
from app.services.trade_executor import TradeExecutor
from app.services.vault_service import VaultService
from app.tasks.scheduler import register_jobs, safe


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings)

    # Schema management: for sqlite we fall back to metadata.create_all()
    # (fast test path). For Postgres/production, operators should run
    # `alembic upgrade head` as a deployment step before the app boots.
    if settings.database_url.startswith(("sqlite", "sqlite+aiosqlite")):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    session_factory = make_session_factory(engine)

    gamma = PolymarketGammaHttpClient(base_url=settings.polymarket_gamma_api_url)
    binance = BinanceHttpClient(base_url=settings.binance_api_url)
    fear_greed = FearGreedHttpClient(base_url=settings.fear_greed_api_url)
    news = CryptoPanicHttpClient(
        base_url=settings.cryptopanic_api_url,
        api_key=settings.cryptopanic_api_key,
    )
    clob = PolymarketCLOBHttpClient(
        base_url=settings.polymarket_clob_api_url,
        api_key=settings.polymarket_api_key,
        api_secret=settings.polymarket_api_secret,
        passphrase=settings.polymarket_passphrase,
    )
    vault = (
        VaultChainClient(
            rpc_url=settings.polygon_rpc_url,
            vault_address=settings.vault_contract_address,
            admin_private_key=settings.admin_private_key,
        )
        if settings.vault_contract_address and settings.polygon_rpc_url
        else _UnconfiguredVault()
    )
    openai = (
        OpenAIHttpClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        if settings.openai_api_key
        else _UnconfiguredOpenAI()
    )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.gamma_client = gamma
    app.state.binance_client = binance
    app.state.fear_greed_client = fear_greed
    app.state.news_client = news
    app.state.clob_client = clob
    app.state.vault_client = vault
    app.state.openai_client = openai

    scheduler = AsyncIOScheduler()
    app.state.scheduler = scheduler

    def _svc_factory(session_maker=session_factory):
        async def _new_session():
            async with session_maker() as s:
                yield s
        return _new_session

    async def _job_scan() -> None:
        async with session_factory() as session:
            svc_gate = VaultService(session=session, vault=None)
            if await svc_gate.is_paused():
                return
            scanner = MarketScanner(gamma=gamma, repo=SqlAlchemyMarketRepository(session))
            await scanner.scan_today()
            await session.commit()

    async def _job_aggregate() -> None:
        # Aggregator output is used synchronously by the predictor job; at
        # scheduled time we simply warm the adapter caches by running a
        # collect_for on the latest market. If there is none, no-op.
        async with session_factory() as session:
            svc_gate = VaultService(session=session, vault=None)
            if await svc_gate.is_paused():
                return
            repo = SqlAlchemyMarketRepository(session)
            market = await repo.get_latest()
            if market is None:
                return
            aggregator = DataAggregator(binance=binance, fear_greed=fear_greed, news=news)
            await aggregator.collect_for(market)

    async def _job_predict() -> None:
        async with session_factory() as session:
            svc_gate = VaultService(session=session, vault=None)
            if await svc_gate.is_paused():
                return
            market = await SqlAlchemyMarketRepository(session).get_latest()
            if market is None:
                return
            bundle = await DataAggregator(
                binance=binance, fear_greed=fear_greed, news=news
            ).collect_for(market)
            predictor = AIPredictor(
                openai=openai,
                repo=SqlAlchemyPredictionRepository(session),
                model=settings.openai_model,
            )
            await predictor.predict(market, bundle)
            await session.commit()

    async def _job_generate() -> None:
        async with session_factory() as session:
            svc_gate = VaultService(session=session, vault=None)
            if await svc_gate.is_paused():
                return
            market_repo = SqlAlchemyMarketRepository(session)
            market = await market_repo.get_latest()
            if market is None or market.id is None:
                return
            prediction = await SqlAlchemyPredictionRepository(session).get_latest_for_market(market.id)
            if prediction is None:
                return
            strategy_repo = SqlAlchemyStrategyRepository(session)
            # Use current vault TVL if available, else fallback sizing assumption.
            from decimal import Decimal
            try:
                balance = await vault.total_assets()
            except Exception:
                balance = Decimal("0")
            if balance <= 0:
                balance = Decimal("100000")  # documented default
            gen = StrategyGenerator(vault_balance=balance)
            strategy = gen.generate(prediction=prediction, market=market)
            await strategy_repo.save(strategy)
            await session.commit()

    async def _job_execute() -> None:
        async with session_factory() as session:
            svc_gate = VaultService(session=session, vault=None)
            if await svc_gate.is_paused():
                return
            market = await SqlAlchemyMarketRepository(session).get_latest()
            if market is None or market.id is None:
                return
            strategy = await SqlAlchemyStrategyRepository(session).get_latest_for_market(market.id)
            if strategy is None or strategy.status != "pending":
                return
            executor = TradeExecutor(
                clob=clob, vault=vault,
                strategy_repo=SqlAlchemyStrategyRepository(session),
                trade_repo=SqlAlchemyTradeRepository(session),
            )
            await executor.execute(strategy=strategy, market=market)
            await session.commit()

    async def _job_snapshot() -> None:
        async with session_factory() as session:
            try:
                await VaultService(session=session, vault=vault).snapshot()
                await session.commit()
            except Exception:
                await session.rollback()

    async def _job_health() -> None:
        # Ping the DB — the scheduler log itself is the health signal.
        async with session_factory() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))

    register_jobs(
        scheduler,
        scan=lambda: safe(_job_scan, "market_scan"),
        aggregate=lambda: safe(_job_aggregate, "data_aggregate"),
        predict=lambda: safe(_job_predict, "ai_predict"),
        generate=lambda: safe(_job_generate, "strategy_gen"),
        execute=lambda: safe(_job_execute, "trade_execute"),
        snapshot=lambda: safe(_job_snapshot, "vault_snapshot"),
        health=lambda: safe(_job_health, "health_check"),
    )

    scheduler.start()

    # Monitor loop (persistent asyncio task).
    async def _monitor_loop():
        # Each iteration opens its own session so we don't leak one across sleeps.
        from app.repositories.market_repository_sa import SqlAlchemyMarketRepository as _MR
        while True:
            try:
                async with session_factory() as session:
                    monitor = PositionMonitor(
                        clob=clob,
                        vault=vault,
                        strategy_repo=SqlAlchemyStrategyRepository(session),
                        trade_repo=SqlAlchemyTradeRepository(session),
                        market_repo=_MR(session),
                    )
                    await monitor.check_once()
                    await session.commit()
            except Exception:
                pass
            await asyncio.sleep(10)

    app.state.monitor_task = asyncio.create_task(_monitor_loop())

    try:
        yield
    finally:
        app.state.monitor_task.cancel()
        try:
            await app.state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
        scheduler.shutdown(wait=False)

        await gamma.aclose()
        await binance.aclose()
        await fear_greed.aclose()
        await news.aclose()
        await clob.aclose()
        if isinstance(openai, OpenAIHttpClient):
            await openai.aclose()
        await engine.dispose()


class _UnconfiguredOpenAI:  # pragma: no cover - defensive runtime stub
    async def predict(self, **_kwargs):
        raise RuntimeError(
            "OpenAI client not configured. Set OPENAI_API_KEY and wire a real client in app.main.lifespan"
        )


class _UnconfiguredVault:  # pragma: no cover - defensive runtime stub
    async def total_assets(self):
        raise RuntimeError("VaultClient not configured; set VAULT_CONTRACT_ADDRESS and POLYGON_RPC_URL")

    async def share_price(self):
        raise RuntimeError("VaultClient not configured")

    async def available_balance(self):
        raise RuntimeError("VaultClient not configured")

    async def withdraw_to_strategy(self, amount):
        raise RuntimeError("VaultClient not configured")

    async def deposit_from_strategy(self, amount):
        raise RuntimeError("VaultClient not configured")


app = FastAPI(title="PolyPredict AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in get_settings().cors_allow_origins.split(",")
        if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets_router.router, prefix="/api/v1")
app.include_router(predictions_router.router, prefix="/api/v1")
app.include_router(strategies_router.router, prefix="/api/v1")
app.include_router(trades_router.router, prefix="/api/v1")
app.include_router(stats_router.router, prefix="/api/v1")
app.include_router(system_router.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
