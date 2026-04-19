# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This is a multi-component project for an AI-driven Polymarket prediction vault.

- `contracts/` — Hardhat + TypeScript Solidity project (PolyVault ERC-4626 UUPS).
- `backend/` — Python 3.12 / FastAPI service. Built via TDD across M0–M8; see `docs/superpowers/specs/2026-04-19-backend-v1-design.md` for the design and milestone breakdown.
- `docs/PRD-smart-contract.md` — contract spec.
- `docs/PRD-backend.md` — backend spec (incorporates the T+2 market selection rule).
- `docs/PRD-frontend.md` — frontend spec (Next.js 14 dashboard, not yet built).

When asked to "build the frontend," start from `docs/PRD-frontend.md`.

## Smart Contract (`contracts/`)

Run all `npm` commands from inside `contracts/`. The hardhat config remaps `sources` to `./src` (not the default `./contracts`), so contracts live in `contracts/src/`.

```bash
npm run compile              # hardhat compile (regenerates typechain-types/)
npm test                     # hardhat test (all tests)
npm run test:coverage        # solidity-coverage report
npm run node                 # local hardhat node on :8545
npm run deploy:local         # deploy via UUPS proxy to localhost
npm run deploy:amoy          # Polygon Amoy testnet
npm run deploy:polygon       # Polygon mainnet
npm run clean                # clear cache/ and artifacts/

# Run a single test by name pattern:
npx hardhat test --grep "should execute withdrawal after delay"
```

Deploys read `USDC_ADDRESS`, `STRATEGIST_ADDRESS`, `GUARDIAN_ADDRESS`, `FEE_RECIPIENT` from env (`.env` in `contracts/`); upgrades require `VAULT_PROXY_ADDRESS`. Networks (`amoy`, `polygon`) need `PRIVATE_KEY` and `*_RPC_URL` — see `.env.example`.

## Architecture: PolyVault

`PolyVault` (`src/PolyVault.sol`) is an ERC-4626 USDC vault deployed behind a UUPS proxy. Three architectural choices to keep in mind when modifying it:

1. **Direct withdraw/redeem are intentionally disabled.** `withdraw()`, `redeem()`, `maxWithdraw()`, `maxRedeem()` are overridden to revert / return 0. Users must go through the three-step delayed flow: `requestWithdraw(shares)` → wait `withdrawalDelay` → `executeWithdraw()` (or `cancelWithdraw()`). Shares are escrowed on the vault address while pending. Do not "fix" the disabled methods — that's the security model (anti-flash-loan share-price manipulation).

2. **`totalAssets()` includes off-chain strategy debt.** It returns `vault USDC balance + strategyDebt`. The strategist pulls funds via `withdrawToStrategy()` (capped at `maxStrategyAllocation` bps of `totalAssets()`) and returns them via `depositFromStrategy()`. Profit (returned amount > debt) auto-distributes `performanceFee` bps to `feeRecipient`. Loss simply reduces `strategyDebt` by the returned amount; share price drops accordingly. Anything that changes share accounting must preserve this invariant.

3. **Partial withdrawal on insufficient liquidity.** `executeWithdraw()` checks vault USDC balance; if shares-worth-of-assets exceeds it, it pays out what's available, burns proportional shares, and returns the remaining shares to the user (un-escrowed) so they can request again later.

### Roles

- `DEFAULT_ADMIN_ROLE` — config setters + `_authorizeUpgrade` (UUPS).
- `STRATEGIST_ROLE` — `withdrawToStrategy` / `depositFromStrategy`.
- `GUARDIAN_ROLE` — `pause` / `unpause`.

`whenNotPaused` gates user deposits and `requestWithdraw`, but **not** `executeWithdraw`/`cancelWithdraw` (so users can always exit pending requests) and **not** strategy functions (so the strategist can always return funds).

### Upgrade Safety

Uses `@openzeppelin/hardhat-upgrades` with `kind: "uups"`. When adding state, append to the end — never reorder or insert variables. Run `upgrades.validateUpgrade` (or just `npm test` against the upgrade test path) before deploying a new implementation. The constructor calls `_disableInitializers()`; all setup goes through `initialize(...)` with the 8 parameters in the order shown in `scripts/deploy-vault.ts`.

### Testing Conventions

- `MockUSDC` (`src/mocks/MockUSDC.sol`) is a 6-decimal ERC20 with public `mint` for tests only — never deploy it to a live network.
- Tests use `loadFixture(deployFixture)` and `time.increase(...)` from `@nomicfoundation/hardhat-toolbox/network-helpers` to advance past `withdrawalDelay`.
- USDC amounts in tests use the `usdc(n)` helper (parses with 6 decimals); on-chain USDC on Polygon is also 6 decimals — don't assume 18.

## Solidity Conventions

- Pragma `^0.8.28`, optimizer 200 runs, evm `cancun`. Match this when adding new contracts.
- Custom errors (not `require` strings) — see the `// ========== ERRORS ==========` block in `PolyVault.sol`.
- `SafeERC20` for all token transfers; `ReentrancyGuardTransient` (transient-storage variant) on state-changing externals.
- Section banner comments (`// ========== SECTION ==========`) are the existing style; preserve them.

## Backend (`backend/`)

Python 3.12 FastAPI single-process monolith. Package manager: `uv`. Run all commands from `backend/`.

```bash
cd backend
uv sync                            # install deps (one-time)
uv run pytest                      # 99 unit+integration tests (~15s)
uv run pytest -m live              # 5 live smoke tests vs real external APIs (skipped by default)
uv run uvicorn app.main:app        # boot dev server on :8000
uv run alembic upgrade head        # apply migrations (Postgres deploys)
docker-compose -f docker/docker-compose.yml up --build    # full stack w/ Postgres
```

### Architectural rules (enforced in tests)

1. **Services depend only on Protocols, never on SQLAlchemy/httpx/web3 directly.** All 6 external clients (Polymarket Gamma/CLOB, Binance, alternative.me Fear & Greed, CryptoPanic, OpenAI, PolyVault chain) are defined in `app/adapters/protocols.py`. Every Protocol has a matching in-memory `Fake*` in `tests/fakes/` plus a real HTTP/web3 impl in `app/adapters/`. Adding a service that imports `httpx` directly breaks the test pipeline.

2. **Pipeline: Scanner → Aggregator → Predictor → StrategyGenerator → TradeExecutor → PositionMonitor.** Each service has a single async entry method (`scan_today`, `collect_for`, `predict`, `generate`, `execute`/`close_position`, `check_once`). They're wired by APScheduler cron jobs in `app/tasks/scheduler.py` (registered in `app/main.py` lifespan).

3. **Strategy generator is a pure synchronous function with three hard gates.** `abs(edge) >= 0.25` AND `confidence >= 0.6` AND AI's `recommended_action` must match the edge sign. Failing any gate produces a `Strategy(action="skip", status="skipped", skip_reason=...)` that's still persisted for audit.

4. **Money precision: `Numeric(38, 18)` everywhere.** SQLite stores Numeric as REAL (test asserts use `abs(...) < Decimal("0.000001")` tolerance); Postgres round-trips exactly.

5. **Pause flag lives in `system_logs` as a sentinel row** (`source='system.pause', message='paused'`). Every scheduled job checks `VaultService.is_paused()` before running. `POST /api/v1/system/{pause,resume}` toggle it.

6. **Schema management:** sqlite (test/local) uses `Base.metadata.create_all` in the lifespan. Postgres/prod runs `alembic upgrade head` (the Dockerfile CMD does this automatically before uvicorn starts).

### Testing conventions

- `@pytest.mark.live` — real external API calls (Binance, Polymarket, Fear & Greed). Skipped by default via `pyproject.toml` `addopts = "-m 'not live'"`; run manually with `uv run pytest -m live`.
- All DB-backed integration tests use sqlite `:memory:` + `StaticPool` so multiple connections share the same database within a test.
- Inject `clock: Callable[[], datetime]` into services (`MarketScanner`, `PositionMonitor`, `VaultService`) for deterministic time-based tests.
- `FastAPI dependency_overrides` wiring pattern: override at the provider level (e.g., `get_market_scanner`, `get_ai_predictor`) so the real dep chain still executes in tests.

### 25% edge rule (`app/services/strategy_generator.py`)

This is the project's core trading discipline. The system ONLY trades when the AI's predicted probability differs from the Polymarket Yes price by ≥ 25 percentage points AND the AI's confidence is ≥ 60%. Per PRD §3.4: small edges on an efficient market are noise, not alpha. Don't weaken this without discussing with the user first.
