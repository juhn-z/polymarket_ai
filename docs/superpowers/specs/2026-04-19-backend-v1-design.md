# Polymarket AI Backend — v1 Design Spec

**Date:** 2026-04-19
**Status:** Approved (auto-mode brainstorm; user requested immediate implementation)
**Source PRD:** [`docs/PRD-backend.md`](../../PRD-backend.md)

This spec captures the v1 architecture for the Python backend. Implementation proceeds incrementally per `# 11. Implementation Order` below; each milestone is end-to-end testable.

---

## 1. Locked Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Data sources (v1) | **Balanced**: Binance + Alternative.me + funding rate + long/short ratio + CryptoPanic + OpenAI. **Excluded** Glassnode (paid), social sentiment | Free + non-paid only; production-realistic data density |
| 2 | External API mocking | **Protocol + in-memory Fake** (default tests) + `@pytest.mark.live` smoke tests (manual) | Fast/stable CI; live tests catch schema drift |
| 3 | Scheduler | **APScheduler `AsyncIOScheduler`** (in-process) | Zero extra deps; v1 doesn't need horizontal scale |
| 4 | Admin auth | **Bearer Token** (static `ADMIN_API_KEY` in env) | v1 operator = developer; SIWE/JWT deferred |
| 5 | Web3/contract tests | **Protocol `VaultClient`** + `web3.py` real impl + Hardhat fork for `live` integration | Same discipline as other adapters |
| 6 | Spec depth | **Module-level only**, not per-function | User chose monolithic spec but incremental implementation |

---

## 2. Process Topology

Single-process monolith for v1: FastAPI + APScheduler + WebSocket all in one ASGI worker.

```
┌──────────────── uvicorn (single process) ─────────────────┐
│                                                            │
│  FastAPI app                                               │
│  ├─ HTTP routers (/api/v1/*)                               │
│  ├─ APScheduler (AsyncIOScheduler) — 8 jobs                │
│  ├─ Background WS client (Polymarket price feed)           │
│  └─ Lifespan (startup/shutdown wires services + scheduler) │
│                                                            │
│  Service layer (pure logic, DI'd protocols + repos)        │
│  └─ MarketScanner / DataAggregator / AIPredictor           │
│     StrategyGenerator / TradeExecutor / PositionMonitor    │
│     VaultService                                            │
│                                                            │
│  Adapter layer (Protocols + real impls)                    │
│  └─ PolymarketGamma / PolymarketCLOB / Binance /           │
│     FearGreed / CryptoPanic / OpenAI / VaultClient         │
│                                                            │
│  Repository layer (SQLAlchemy 2.0 async)                   │
│  └─ MarketRepo / PredictionRepo / StrategyRepo / ...       │
│                                                            │
└────────────┬─────────────────────────────┬─────────────────┘
             ▼                             ▼
        PostgreSQL                External APIs / Polygon RPC
```

**Hard architectural rule:** the Service layer must not import FastAPI, SQLAlchemy, web3.py, or any HTTP client. Only Protocol-typed dependencies. This is what makes the in-memory pipeline test possible.

---

## 3. Module Boundaries (Protocols)

Each external dependency has a `Protocol` + a Fake. Service code only sees the Protocol.

```python
# app/adapters/protocols.py
class PolymarketGammaClient(Protocol):
    async def search_events(self, tag: str, active: bool) -> list[Event]: ...
    async def get_event_markets(self, event_id: str) -> list[GammaMarket]: ...

class PolymarketCLOBClient(Protocol):
    async def place_order(self, token_id: str, side: str, price: Decimal, size: Decimal) -> Order: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def get_order(self, order_id: str) -> Order: ...
    async def get_positions(self) -> list[Position]: ...

class BinanceClient(Protocol):
    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[Kline]: ...
    async def get_funding_rate(self, symbol: str) -> Decimal: ...
    async def get_long_short_ratio(self, symbol: str, period: str) -> Decimal: ...

class FearGreedClient(Protocol):
    async def get_index(self, days: int = 7) -> list[FearGreedPoint]: ...

class CryptoPanicClient(Protocol):
    async def get_btc_news(self, limit: int = 10) -> list[NewsItem]: ...

class OpenAIClient(Protocol):
    async def predict(self, system: str, user: str, response_schema: dict) -> dict: ...

class VaultClient(Protocol):
    async def total_assets(self) -> int: ...
    async def share_price(self) -> Decimal: ...
    async def withdraw_to_strategy(self, amount: int) -> TxReceipt: ...
    async def deposit_from_strategy(self, amount: int) -> TxReceipt: ...
```

### Service signatures

```python
class MarketScanner:
    async def scan_today(self) -> Market

class DataAggregator:
    async def collect_for(self, market: Market) -> MarketDataBundle

class AIPredictor:
    async def predict(self, market: Market, bundle: MarketDataBundle) -> Prediction

class StrategyGenerator:
    def generate(self, prediction: Prediction, market: Market, vault_balance: int) -> Strategy

class TradeExecutor:
    async def execute(self, strategy: Strategy) -> Trade
    async def close_position(self, strategy: Strategy, reason: str) -> Trade

class PositionMonitor:
    async def run_forever(self) -> None
    async def check_once(self) -> None  # for tests

class VaultService:
    async def snapshot(self) -> VaultSnapshot
    async def get_overview_stats(self) -> OverviewStats
    async def get_leaderboard(self) -> list[LeaderboardEntry]
```

---

## 4. Data Model (PostgreSQL via SQLAlchemy 2.0 async)

7 tables per PRD §5.1. All money fields use `Numeric(38, 18)` (no float).

| Table | Key columns | Relationships |
|---|---|---|
| `markets` | polymarket_condition_id, polymarket_token_id, question, price_threshold, target_date, current_yes_price, status, resolution | 1:N predictions |
| `predictions` | market_id (FK), predicted_probability, confidence, direction, key_factors (JSONB), risk_factors (JSONB), reasoning, recommended_action, market_probability, edge, model_version, data_snapshot (JSONB) | 1:1 strategy |
| `strategies` | prediction_id (FK), market_id (FK), action, side, position_size, entry_price, take_profit, stop_loss, kelly_fraction, status | 1:N trades |
| `trades` | strategy_id (FK), market_id (FK), polymarket_order_id, side, action (buy/sell), amount, price, shares, status, fee, pnl, filled_at, closed_at | — |
| `vault_snapshots` | total_assets, share_price, tvl, depositor_count, deployed_amount, snapshot_at | time-series |
| `users` | wallet_address (PK), first_deposit_at | — (computed via vault events for leaderboard) |
| `system_logs` | level, source, message, context (JSONB), trace_id, created_at | audit / observability |

**Constraints:**
- `markets.polymarket_condition_id` unique
- `predictions(market_id, created_at)` index (latest-per-market query)
- `trades.polymarket_order_id` unique
- All tables: `created_at`, `updated_at` (auto-managed)

**Migrations:** Alembic. Initial revision `0001_initial.py` creates all 7 tables.

---

## 5. REST API Surface

20 endpoints, all under `/api/v1/`, Pydantic v2 schemas:

### Public (no auth)
```
GET  /markets/today
GET  /markets/history?page=&size=
GET  /markets/{id}
GET  /predictions/today
GET  /predictions/history?page=&size=
GET  /predictions/{id}
GET  /strategies/active
GET  /strategies/history?page=&size=
GET  /trades/active
GET  /trades/history?page=&size=
GET  /trades/{id}
GET  /stats/overview
GET  /stats/leaderboard
GET  /stats/daily?days=30
GET  /stats/vault
GET  /health
```

### Admin (`Authorization: Bearer $ADMIN_API_KEY`)
```
POST /markets/scan
POST /predictions/trigger
POST /system/pause
POST /system/resume
GET  /system/status
```

**Auth dependency:** `Depends(require_admin)` reads `Authorization` header, compares against `settings.ADMIN_API_KEY` (constant-time compare).

---

## 6. Scheduling (APScheduler)

```python
# app/tasks/scheduler.py
def register_jobs(scheduler: AsyncIOScheduler, services: ServiceRegistry) -> None:
    scheduler.add_job(services.scanner.scan_today, CronTrigger(hour=0, minute=0))
    scheduler.add_job(services.aggregator.collect_today, CronTrigger(hour=1, minute=0))
    scheduler.add_job(services.predictor.predict_today, CronTrigger(hour=2, minute=0))
    scheduler.add_job(services.generator.generate_today, CronTrigger(hour=2, minute=30))
    scheduler.add_job(services.executor.execute_today, CronTrigger(hour=3, minute=0))
    scheduler.add_job(services.vault.snapshot, CronTrigger(minute=0))
    scheduler.add_job(services.health.check, CronTrigger(minute='*/5'))
```

`PositionMonitor.run_forever()` runs as `asyncio.create_task` from lifespan, not via APScheduler (it's a long-running loop, not a periodic job).

**Pause flag:** `system_logs` table has a sentinel row `(source='system', message='paused')`. `TradeExecutor.execute_today` checks for it and short-circuits. `POST /system/pause` inserts/removes it.

---

## 7. Testing Strategy

```
tests/
├── unit/                       # Fast (<1s), no I/O, all deps faked
│   ├── services/               # 1:1 with services/
│   ├── strategy/               # Kelly, take-profit, stop-loss math
│   └── adapters/               # Protocol contract tests (Real impl vs Fake parity)
├── integration/                # FastAPI TestClient + real PostgreSQL (testcontainers) + Fake APIs
│   ├── api/                    # 1 test per endpoint
│   └── pipeline/               # End-to-end: scan→aggregate→predict→strategy→execute (all Fake)
├── live/                       # @pytest.mark.live, CI default skip
│   ├── test_binance_schema.py
│   ├── test_polymarket_gamma_schema.py
│   ├── test_polymarket_clob_schema.py
│   ├── test_fear_greed.py
│   ├── test_cryptopanic.py
│   └── test_vault_hardhat_fork.py    # spawns hardhat node, deploys contracts, exercises VaultClient
└── fakes/
    ├── fake_polymarket_gamma.py
    ├── fake_polymarket_clob.py
    ├── fake_binance.py
    ├── fake_fear_greed.py
    ├── fake_cryptopanic.py
    ├── fake_openai.py
    └── fake_vault.py
```

**Pytest config:**
- `pyproject.toml [tool.pytest.ini_options]`: `markers = ["live: tests against real external APIs"]`
- Default invocation: `pytest` (excludes `live` via `addopts = "-m 'not live'"`)
- Live: `pytest -m live`

**Coverage targets:** services / strategy ≥ 90%; adapters ≥ 70% (rest covered by live).

**TDD discipline:** every feature follows red → green → refactor. No production code without a failing test that requires it.

---

## 8. Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + lifespan (wires DI)
│   ├── config.py               # pydantic-settings
│   ├── db.py                   # async engine + session factory
│   ├── auth.py                 # require_admin dependency
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── __init__.py
│   │   ├── base.py             # Base, mixins (TimestampMixin)
│   │   ├── market.py
│   │   ├── prediction.py
│   │   ├── strategy.py
│   │   ├── trade.py
│   │   ├── vault_snapshot.py
│   │   ├── user.py
│   │   └── system_log.py
│   ├── schemas/                # Pydantic v2 (request/response)
│   ├── repositories/           # data access (one file per aggregate root)
│   ├── services/               # 7 services
│   │   ├── market_scanner.py
│   │   ├── data_aggregator.py
│   │   ├── ai_predictor.py
│   │   ├── strategy_generator.py
│   │   ├── trade_executor.py
│   │   ├── position_monitor.py
│   │   └── vault_service.py
│   ├── adapters/
│   │   ├── protocols.py        # all Protocols
│   │   ├── polymarket_gamma.py
│   │   ├── polymarket_clob.py
│   │   ├── binance.py
│   │   ├── fear_greed.py
│   │   ├── cryptopanic.py
│   │   ├── openai_client.py
│   │   └── vault_chain.py      # web3.py impl
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # DI providers (db session, services, auth)
│   │   └── v1/
│   │       ├── markets.py
│   │       ├── predictions.py
│   │       ├── strategies.py
│   │       ├── trades.py
│   │       ├── stats.py
│   │       └── system.py
│   ├── tasks/
│   │   └── scheduler.py
│   └── utils/
│       ├── indicators.py       # uses ta library
│       ├── kelly.py
│       └── logger.py           # structlog
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/                      # see §7
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml      # postgres + backend
├── pyproject.toml              # uv-managed, Python 3.11+
├── alembic.ini
├── conftest.py                 # shared fixtures
└── .env.example
```

**Deps highlights:** `fastapi`, `pydantic-settings`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `httpx`, `apscheduler`, `tenacity`, `structlog`, `ta`, `openai`, `web3`. Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `testcontainers[postgres]`, `respx` (for adapter unit tests).

---

## 9. Error Handling & Observability

| Failure | Response |
|---|---|
| External API 5xx / timeout | `tenacity` exp-backoff ×3; final fail → `system_logs` ERROR + alert event |
| OpenAI returns non-JSON | Pydantic validation fails → mark prediction.status=failed, skip day |
| Polymarket 429 | Exp-backoff + adapter-level leaky bucket |
| Chain tx revert | Bump gas + retry; final fail → strategy.status=failed |
| WebSocket disconnect | Auto-reconnect (exp-backoff); fall back to 30s REST polling |
| DB connection drop | SQLAlchemy `pool_pre_ping=True` + auto-reconnect |

**Logging:** `structlog` JSON output. Each scheduled job generates a `trace_id` (uuid4) propagated via `contextvars` through all logs of that run.

**Metrics:** No Prometheus in v1. Key events written to `system_logs`; SQL queries cover observability needs.

---

## 10. Configuration

`config.yaml` (committed, no secrets) + `.env` (gitignored, secrets) merged by `pydantic-settings`. The `${VAR_NAME}` syntax in YAML is interpolated from env at load time.

```env
# .env (operator fills in)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/polypredict
ADMIN_API_KEY=...
POLYMARKET_API_KEY=...
POLYMARKET_API_SECRET=...
POLYMARKET_PASSPHRASE=...
OPENAI_API_KEY=...
CRYPTOPANIC_API_KEY=...
ADMIN_PRIVATE_KEY=0x...               # for vault.withdrawToStrategy / depositFromStrategy
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/...
VAULT_CONTRACT_ADDRESS=0x...
USDC_CONTRACT_ADDRESS=0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359
```

`.env.example` ships in repo with placeholder values.

---

## 11. Implementation Order

Spec is monolithic but implementation MUST be incremental. Each milestone is end-to-end testable (TDD: write failing test first, then minimum code to pass, then refactor):

| M | Scope | Acceptance |
|---|---|---|
| **M0** | Scaffold: pyproject + uv + packages + settings + db engine + alembic init + pytest config + first migration (markets table) + structlog + `/health` endpoint | `pytest` green; `uvicorn app.main:app` boots; `GET /health` returns 200 |
| **M1** | **Market Scanner E2E**: `PolymarketGammaClient` Protocol + Fake + real impl + `MarketScanner.scan_today` + `MarketRepo` + `GET /api/v1/markets/today` + `POST /api/v1/markets/scan` (admin) | Unit tests for Scanner logic (filtering 35-65%, picking by liquidity); integration test scans → DB → endpoint returns market |
| **M2** | **Data Aggregator**: Binance + FearGreed + CryptoPanic adapters + indicators (RSI/MACD/BB/EMA/ATR) + `DataAggregator.collect_for` returning `MarketDataBundle` | Unit tests per indicator + per adapter (Fake); integration test collects bundle for a known market |
| **M3** | **AI Predictor**: OpenAI adapter + prompt template + JSON schema validation + `Prediction` model + `/api/v1/predictions/*` GET endpoints + admin trigger | Unit tests with FakeOpenAI returning canned responses; integration test predicts for a known bundle |
| **M4** | **Strategy Generator**: Kelly util + take-profit/stop-loss + edge/confidence gates + `Strategy` model + `/api/v1/strategies/*` | Pure-function tests with high coverage; integration test runs scan→aggregate→predict→generate end-to-end with Fakes |
| **M5** | **Trade Executor + VaultClient**: `web3.py` integration + `PolymarketCLOBClient` + `TradeExecutor.execute` + `Trade` model + `/api/v1/trades/*` + Hardhat fork live test | Unit tests with FakeVault + FakeCLOB; live test deploys vault + exercises real `withdrawToStrategy` |
| **M6** | **Position Monitor**: WebSocket client + monitor loop + take-profit/stop-loss/pre-resolution close + reconnect logic | Unit test with FakeCLOB ticking prices; integration test triggers close-on-take-profit |
| **M7** | **Stats / Leaderboard / System**: `VaultService.snapshot/overview/leaderboard/daily` + remaining endpoints + scheduler wiring + pause flag | Snapshot job runs hourly in test; overview/leaderboard return correct aggregates |
| **M8** | **Hardening**: Dockerfile + docker-compose + production logging + retry/backoff polish + README updates | `docker-compose up` boots full stack with Postgres |

Implementation begins immediately with **M0 + M1**.

---

## 12. Out of Scope (v1)

- Glassnode / on-chain data (paid)
- LunarCrush / social sentiment
- Prometheus / Grafana metrics
- Celery / Redis queue
- SIWE / wallet-signature admin auth
- Multi-strategy / multi-market parallel trading (v1 = one market/day)
- Backtesting framework
- Frontend (separate project)

---

## 13. Open Questions (resolved during implementation)

These are intentionally deferred — not blocking:

1. Exact OpenAI prompt wording — iterate against fixture market data after M3 lands.
2. Kelly formula edge cases (very small denominators) — TDD will surface, fix in unit tests.
3. WebSocket vs REST polling threshold for monitor — start with WS, fall back to 30s REST.
4. Hardhat fork RPC URL for `live` tests — use `localhost:8545` spawned by test fixture.
