# Frontend + Local Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Polymarket AI Vault stack so it runs locally end-to-end — backend hardened for demo (only OpenAI + Polymarket keys required), Hardhat localhost auto-deploy, full Next.js 14 dashboard with wallet integration, and a one-command demo path.

**Architecture:** Three layers running in parallel on `localhost`:
1. **Hardhat node** (`:8545`, chainId `31337`) — deploys `MockUSDC` + `PolyVault` proxy on startup, mints test USDC to default accounts; address book exported to `contracts/exports/localhost.json`.
2. **FastAPI backend** (`:8000`) — reads chain via `web3.py`, runs APScheduler pipeline, serves `/api/v1/*`. CORS-enabled for frontend. Treats `CRYPTOPANIC_API_KEY=""` and other optional keys as graceful no-ops.
3. **Next.js 14 frontend** (`:3000`) — wagmi v2 + RainbowKit + viem; reads on-chain vault state directly via wagmi hooks; reads off-chain stats/predictions via TanStack Query → backend.

**Tech Stack:**
- Frontend: Next.js 14 (App Router), TypeScript 5.4, Tailwind 3.4, shadcn/ui, wagmi v2, viem 2.x, @rainbow-me/rainbowkit 2.x, @tanstack/react-query 5.x, zustand 4.x, recharts 2.x, framer-motion 11, lucide-react, sonner, vitest, @playwright/test, pnpm.
- Backend: existing stack — fastapi, sqlalchemy 2 async, apscheduler, pydantic v2, web3.py, openai. New: `fastapi.middleware.cors.CORSMiddleware`, `python-multipart` (already there).
- Contracts: existing Hardhat 2.22 + Solidity 0.8.28; add `concurrently` to root package.json for orchestration.

---

## File Structure

### New files
```
contracts/
├── scripts/
│   ├── deploy-local-full.ts            # Deploys MockUSDC + PolyVault, mints USDC, writes localhost.json
│   └── export-abi.ts                   # Strips ABI from artifacts into exports/abi/
├── exports/
│   ├── localhost.json                  # gitignored; written by deploy-local-full
│   └── abi/
│       ├── PolyVault.json              # ABI only, committed
│       └── MockUSDC.json               # ABI only, committed
└── test/
    └── deploy-local-full.test.ts       # Sanity test: script writes correct JSON shape

backend/
├── tests/unit/adapters/
│   └── test_cryptopanic_graceful.py    # graceful when key empty
├── tests/integration/api/
│   └── test_cors.py                    # OPTIONS / Access-Control-Allow-Origin header test
└── scripts/
    └── seed_demo.py                    # Idempotent admin-API-driven demo data seeding

frontend/                                   # entire tree is new
├── package.json
├── pnpm-lock.yaml                          # generated
├── tsconfig.json
├── next.config.mjs
├── postcss.config.mjs
├── tailwind.config.ts
├── components.json                         # shadcn/ui config
├── .env.local.example
├── .eslintrc.json
├── .gitignore
├── playwright.config.ts
├── vitest.config.ts
├── public/
│   └── favicon.ico
├── src/
│   ├── app/
│   │   ├── layout.tsx                      # Root layout: providers + Header + Footer
│   │   ├── page.tsx                        # Dashboard (/)
│   │   ├── globals.css                     # Tailwind base + design tokens
│   │   ├── vault/page.tsx
│   │   ├── predictions/page.tsx
│   │   ├── predictions/[id]/page.tsx
│   │   ├── leaderboard/page.tsx
│   │   └── admin/page.tsx
│   ├── components/
│   │   ├── layout/{Header,Footer,MobileNav,ThemeToggle}.tsx
│   │   ├── dashboard/{StatsCards,TodayPrediction,PnLChart,RecentTrades}.tsx
│   │   ├── vault/{VaultInfo,DepositForm,WithdrawForm,PendingWithdrawals,SharePriceChart}.tsx
│   │   ├── predictions/{PredictionList,PredictionCard,PredictionDetail}.tsx
│   │   ├── leaderboard/LeaderboardTable.tsx
│   │   ├── admin/{SystemStatus,AdminActions}.tsx
│   │   └── ui/                             # shadcn/ui generated
│   ├── hooks/
│   │   ├── useVault.ts
│   │   ├── useVaultWrite.ts
│   │   ├── useUSDC.ts
│   │   ├── useMarkets.ts
│   │   ├── usePredictions.ts
│   │   ├── useStrategies.ts
│   │   ├── useTrades.ts
│   │   ├── useStats.ts
│   │   ├── useSystem.ts
│   │   └── useBTCPrice.ts
│   ├── lib/
│   │   ├── api.ts                          # fetch wrapper, throws ApiError
│   │   ├── contracts.ts                    # ABIs + addresses by chainId
│   │   ├── chains.ts                       # hardhat localhost chain def
│   │   ├── wagmi.ts                        # wagmi config
│   │   ├── format.ts                       # USDC, %, time formatters
│   │   └── utils.ts                        # cn() shadcn helper
│   ├── providers/{Web3Provider,QueryProvider,ThemeProvider}.tsx
│   ├── store/admin.ts                      # zustand store for admin token
│   ├── types/{api,contracts}.ts            # TypeScript types mirroring backend schemas + ABIs
│   └── tests/
│       ├── unit/
│       │   ├── format.test.ts
│       │   └── api.test.ts
│       └── e2e/
│           ├── dashboard.spec.ts
│           └── vault.spec.ts

scripts/                                    # repo-root orchestration
├── dev.sh                                  # starts hardhat + backend + frontend
└── seed-demo.sh                            # calls deploy + backend seed

# repo root
├── package.json                            # root, just for `concurrently` orchestration
├── README.md                               # update with full demo walk-through
└── .env.example                            # demo-friendly defaults
```

### Modified files
```
backend/
├── app/main.py                             # add CORSMiddleware
├── app/adapters/cryptopanic.py             # graceful when api_key=""
├── app/services/data_aggregator.py         # tolerate news client failure
├── .env.example                            # mark optional vs required
└── tests/integration/api/test_health.py    # extend to check CORS header

contracts/
├── package.json                            # add `dev:full`, `export:abi` scripts; add deps
└── .gitignore                              # ignore exports/localhost.json

CLAUDE.md                                   # mention frontend/ and dev.sh
README.md                                   # full local-demo walkthrough
```

---

## Phase 0 — Backend Hardening (graceful key-less demo + CORS)

### Task 0.1: CryptoPanic returns empty list when api_key is empty

**Files:**
- Modify: `backend/app/adapters/cryptopanic.py`
- Test: `backend/tests/unit/adapters/test_cryptopanic_graceful.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/adapters/test_cryptopanic_graceful.py
"""CryptoPanicHttpClient must skip the network call when no API key is configured."""
from __future__ import annotations

import httpx
import pytest

from app.adapters.cryptopanic import CryptoPanicHttpClient


@pytest.mark.asyncio
async def test_returns_empty_list_when_api_key_missing():
    """No HTTP call should be made; result is [] so the aggregator can degrade gracefully."""
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        calls.append(str(request.url))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    client = CryptoPanicHttpClient(api_key="", client=httpx.AsyncClient(transport=transport))
    try:
        result = await client.get_btc_news(limit=5)
    finally:
        await client.aclose()

    assert result == []
    assert calls == []  # zero network traffic when key missing


@pytest.mark.asyncio
async def test_calls_api_when_key_present():
    """With a key, behavior is unchanged — network call is made."""
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    client = CryptoPanicHttpClient(api_key="abc123", client=httpx.AsyncClient(transport=transport))
    try:
        await client.get_btc_news(limit=5)
    finally:
        await client.aclose()

    assert len(calls) == 1
    assert "auth_token=abc123" in calls[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/adapters/test_cryptopanic_graceful.py -v`
Expected: First test FAILs with `assert calls == []` — current implementation always calls.

- [ ] **Step 3: Make CryptoPanic skip the call when key empty**

Edit `backend/app/adapters/cryptopanic.py` — replace the `get_btc_news` method body:

```python
    async def get_btc_news(self, limit: int = 10) -> list[NewsItem]:
        # Graceful no-op when no API key is configured (demo / cost-free path).
        # The data aggregator treats an empty news list as "no news signal"
        # rather than an error, per PRD-backend §3.2.4 (news is optional input).
        if not self._api_key:
            return []

        response = await self._client.get(
            f"{self._base_url}posts/",
            params={
                "auth_token": self._api_key,
                "currencies": "BTC",
                "public": "true",
            },
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results", [])[:limit]
        return [_parse(row) for row in rows]
```

- [ ] **Step 4: Verify both tests pass and no regressions**

Run: `cd backend && uv run pytest tests/unit/adapters/ -v`
Expected: All adapter tests PASS (including the existing CryptoPanic HTTP test).

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/cryptopanic.py backend/tests/unit/adapters/test_cryptopanic_graceful.py
git commit -m "feat(backend): cryptopanic gracefully returns [] when api_key is empty"
```

---

### Task 0.2: DataAggregator tolerates news fetch failure

**Files:**
- Modify: `backend/app/services/data_aggregator.py`
- Test: `backend/tests/unit/services/test_data_aggregator.py` (extend)

- [ ] **Step 1: Read current test to know existing patterns**

Read `backend/tests/unit/services/test_data_aggregator.py` to understand the shape of fakes. Add a new test — append at end:

```python
import pytest


class _RaisingNews:
    async def get_btc_news(self, limit: int = 10):
        raise RuntimeError("simulated CryptoPanic outage")


@pytest.mark.asyncio
async def test_aggregator_returns_empty_news_when_news_client_raises(
    binance_with_klines, fear_greed_with_index, market_for_today
):
    """News is best-effort; a 5xx or schema drift must NOT kill prediction."""
    from app.services.data_aggregator import DataAggregator

    aggregator = DataAggregator(
        binance=binance_with_klines,
        fear_greed=fear_greed_with_index,
        news=_RaisingNews(),
    )
    bundle = await aggregator.collect_for(market_for_today)

    assert bundle.news_headlines == []
    # Other fields must still be populated from binance + fear_greed
    assert bundle.btc_current_price > 0
    assert bundle.fear_greed_index is not None
```

If the existing test file does not already define fixtures `binance_with_klines`, `fear_greed_with_index`, `market_for_today`, locate them by reading the file head and reuse them. If they don't exist (named differently), adapt the test to the existing fixture names — keep the assertions identical.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/services/test_data_aggregator.py::test_aggregator_returns_empty_news_when_news_client_raises -v`
Expected: FAIL — `RuntimeError: simulated CryptoPanic outage` propagates.

- [ ] **Step 3: Wrap news call in try/except in the aggregator**

Edit `backend/app/services/data_aggregator.py` — change the news fetch line in `collect_for`:

```python
        try:
            news_items = await self._news.get_btc_news(limit=NEWS_LIMIT)
        except Exception:
            # News is optional. CryptoPanic outages, missing keys, or schema
            # drift should not block the daily prediction (PRD §3.2.4 — news
            # is best-effort context, not a hard input).
            news_items = []
```

- [ ] **Step 4: Run aggregator tests**

Run: `cd backend && uv run pytest tests/unit/services/test_data_aggregator.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data_aggregator.py backend/tests/unit/services/test_data_aggregator.py
git commit -m "feat(backend): aggregator tolerates news client failure (degrade gracefully)"
```

---

### Task 0.3: Add CORS middleware (configurable origins)

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/integration/api/test_cors.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/api/test_cors.py
"""CORS must allow the configured frontend origin (demo: http://localhost:3000)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_localhost_3000():
    with TestClient(app) as client:
        resp = client.options(
            "/api/v1/markets/today",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    # FastAPI's CORS middleware returns 200 for valid preflight
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in resp.headers["access-control-allow-methods"]


def test_cors_simple_get_includes_origin_header():
    with TestClient(app) as client:
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/api/test_cors.py -v`
Expected: FAIL — current app has no CORS middleware so the headers are missing.

- [ ] **Step 3: Add `cors_allow_origins` to settings**

Edit `backend/app/config.py` — add this field inside the `Settings` class (anywhere among the other fields):

```python
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
```

- [ ] **Step 4: Wire the CORS middleware in `main.py`**

Edit `backend/app/main.py`:

a) Add this import near the top (with other fastapi imports):

```python
from fastapi.middleware.cors import CORSMiddleware
```

b) After `app = FastAPI(title="PolyPredict AI Backend", lifespan=lifespan)` (line ~279), add:

```python
_settings_for_cors = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings_for_cors.cors_allow_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 5: Run all integration tests**

Run: `cd backend && uv run pytest tests/integration/ -v`
Expected: all PASS, including the two new CORS tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/config.py backend/tests/integration/api/test_cors.py
git commit -m "feat(backend): CORS middleware (default localhost:3000) for frontend dev"
```

---

### Task 0.4: Update `.env.example` to flag optional keys

**Files:**
- Modify: `backend/.env.example`

- [ ] **Step 1: Rewrite `backend/.env.example`**

Replace its entire contents with:

```env
# ---------------- Required for demo ----------------
# (Hardhat localhost defaults work without further setup once the chain is up)
DATABASE_URL=sqlite+aiosqlite:///./polypredict.db
ADMIN_API_KEY=dev_admin_key
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Polygon RPC + addresses — overwritten by `pnpm dev:contracts` script
POLYGON_RPC_URL=http://127.0.0.1:8545
ADMIN_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
VAULT_CONTRACT_ADDRESS=
USDC_CONTRACT_ADDRESS=

# ---------------- API keys (only OpenAI + Polymarket are required) ----------------
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.4

POLYMARKET_GAMMA_API_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_API_URL=https://clob.polymarket.com
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_PASSPHRASE=

# ---------------- Optional (graceful no-op when blank) ----------------
# Binance + Fear&Greed are public APIs; no key needed.
# CryptoPanic free-tier requires a key; if blank, news is omitted from the bundle.
BINANCE_API_URL=https://api.binance.com
FEAR_GREED_API_URL=https://api.alternative.me/fng/
CRYPTOPANIC_API_URL=https://cryptopanic.com/api/v1/
CRYPTOPANIC_API_KEY=

LOG_LEVEL=INFO
```

The default `ADMIN_PRIVATE_KEY` is the well-known Hardhat account #0 (Foundry / Anvil / Hardhat all use this). It must remain a placeholder for testnet/mainnet deployments. Document this in the file header comment.

- [ ] **Step 2: Verify the file is syntactically valid by loading it**

Run: `cd backend && cp .env.example .env.test && uv run python -c "from app.config import get_settings; get_settings.cache_clear(); import os; os.environ.setdefault('CRYPTOPANIC_API_KEY', ''); print(get_settings().cors_allow_origins)" && rm .env.test`

Expected: prints `http://localhost:3000,http://127.0.0.1:3000` without raising.

- [ ] **Step 3: Commit**

```bash
git add backend/.env.example
git commit -m "docs(backend): mark which keys are optional vs required in .env.example"
```

---

## Phase 1 — Hardhat Localhost Auto-Deploy

### Task 1.1: `deploy-local-full.ts` — deploys MockUSDC + PolyVault, mints USDC

**Files:**
- Create: `contracts/scripts/deploy-local-full.ts`
- Create: `contracts/exports/.gitkeep`
- Modify: `contracts/.gitignore`

- [ ] **Step 1: Add `exports/localhost.json` to gitignore**

Append to `contracts/.gitignore`:

```
# generated address book; ABI/ folder is committed
exports/localhost.json
```

- [ ] **Step 2: Create the deploy script**

Create `contracts/scripts/deploy-local-full.ts`:

```typescript
// Deploys a full local stack:
//   1. MockUSDC (6 decimals)
//   2. PolyVault behind UUPS proxy
//   3. Mints 1,000,000 USDC each to the first 5 Hardhat accounts
//   4. Writes addresses + chain info to contracts/exports/localhost.json
//
// Use:  npx hardhat run scripts/deploy-local-full.ts --network localhost

import { ethers, upgrades, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const SIX_DECIMALS = 1_000_000n;
const SEED_AMOUNT = 1_000_000n * SIX_DECIMALS; // 1,000,000 USDC per account
const NUM_FUNDED = 5;

async function main() {
  if (network.name !== "localhost" && network.name !== "hardhat") {
    throw new Error(`This script is only for localhost / hardhat — got ${network.name}`);
  }

  const signers = await ethers.getSigners();
  const [deployer] = signers;
  console.log(`Deployer: ${deployer.address}`);

  // 1. MockUSDC
  const MockUSDC = await ethers.getContractFactory("MockUSDC");
  const usdc = await MockUSDC.deploy();
  await usdc.waitForDeployment();
  const usdcAddress = await usdc.getAddress();
  console.log(`MockUSDC: ${usdcAddress}`);

  // 2. PolyVault (UUPS proxy)
  const PolyVault = await ethers.getContractFactory("PolyVault");
  const vault = await upgrades.deployProxy(
    PolyVault,
    [
      usdcAddress,
      deployer.address, // admin
      deployer.address, // strategist
      deployer.address, // guardian
      deployer.address, // feeRecipient
      24 * 60 * 60,     // withdrawalDelay = 24h
      8000,             // maxAllocation = 80%
      1000,             // performanceFee = 10%
    ],
    { kind: "uups" }
  );
  await vault.waitForDeployment();
  const vaultAddress = await vault.getAddress();
  const implAddress = await upgrades.erc1967.getImplementationAddress(vaultAddress);
  console.log(`PolyVault proxy: ${vaultAddress}`);
  console.log(`PolyVault impl:  ${implAddress}`);

  // 3. Mint USDC to first NUM_FUNDED accounts
  const funded: { address: string; balance: string }[] = [];
  for (let i = 0; i < Math.min(NUM_FUNDED, signers.length); i++) {
    const tx = await usdc.mint(signers[i].address, SEED_AMOUNT);
    await tx.wait();
    funded.push({ address: signers[i].address, balance: SEED_AMOUNT.toString() });
  }
  console.log(`Minted 1,000,000 USDC to ${funded.length} accounts`);

  // 4. Write address book
  const exportsDir = path.resolve(__dirname, "..", "exports");
  if (!fs.existsSync(exportsDir)) fs.mkdirSync(exportsDir, { recursive: true });

  const addressBook = {
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    network: network.name,
    deployedAt: new Date().toISOString(),
    addresses: {
      MockUSDC: usdcAddress,
      PolyVault: vaultAddress,
      PolyVaultImpl: implAddress,
    },
    deployer: deployer.address,
    funded,
  };

  const outPath = path.join(exportsDir, "localhost.json");
  fs.writeFileSync(outPath, JSON.stringify(addressBook, null, 2));
  console.log(`\nAddress book → ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
```

- [ ] **Step 3: Verify the script compiles**

Run: `cd contracts && npx hardhat compile`
Expected: compiles cleanly (no TypeScript errors).

- [ ] **Step 4: Smoke-run the deploy against an in-process hardhat node**

Run (in one shot — Hardhat starts and tears down its own node when using `--network hardhat`):
```bash
cd contracts && npx hardhat run scripts/deploy-local-full.ts --network hardhat
```
Expected: prints addresses, ends with "Address book → ..."; verify `contracts/exports/localhost.json` was written and has `chainId: 31337`.

- [ ] **Step 5: Commit**

```bash
git add contracts/scripts/deploy-local-full.ts contracts/.gitignore
git commit -m "feat(contracts): deploy-local-full script — vault + USDC + funded accounts"
```

---

### Task 1.2: `export-abi.ts` — copy ABIs into committed `exports/abi/`

**Files:**
- Create: `contracts/scripts/export-abi.ts`

- [ ] **Step 1: Create the script**

Create `contracts/scripts/export-abi.ts`:

```typescript
// Copies ABI from compiled artifacts into contracts/exports/abi/<Name>.json
// (just the abi, not the full artifact) so the frontend can import it
// without depending on Hardhat's artifact layout.
//
// Use:  npx hardhat run scripts/export-abi.ts

import { artifacts } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const TO_EXPORT = ["PolyVault", "MockUSDC"];

async function main() {
  const outDir = path.resolve(__dirname, "..", "exports", "abi");
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  for (const name of TO_EXPORT) {
    const art = await artifacts.readArtifact(name);
    const out = { contractName: name, abi: art.abi };
    fs.writeFileSync(path.join(outDir, `${name}.json`), JSON.stringify(out, null, 2));
    console.log(`Exported ${name} ABI → exports/abi/${name}.json`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
```

- [ ] **Step 2: Add `dev:full` and `export:abi` npm scripts**

Edit `contracts/package.json`. Replace the `scripts` block with:

```json
  "scripts": {
    "compile": "hardhat compile",
    "test": "hardhat test",
    "test:coverage": "hardhat coverage",
    "deploy:local": "hardhat run scripts/deploy-vault.ts --network localhost",
    "deploy:local-full": "hardhat run scripts/deploy-local-full.ts --network localhost",
    "deploy:amoy": "hardhat run scripts/deploy-vault.ts --network amoy",
    "deploy:polygon": "hardhat run scripts/deploy-vault.ts --network polygon",
    "node": "hardhat node",
    "export:abi": "hardhat run scripts/export-abi.ts",
    "clean": "hardhat clean"
  },
```

- [ ] **Step 3: Run `export:abi` and commit the produced ABI files**

Run: `cd contracts && npm run compile && npm run export:abi`
Expected: produces `contracts/exports/abi/PolyVault.json` and `contracts/exports/abi/MockUSDC.json`.

- [ ] **Step 4: Commit**

```bash
git add contracts/scripts/export-abi.ts contracts/package.json contracts/exports/abi/
git commit -m "feat(contracts): export-abi script + ship PolyVault/MockUSDC ABI for frontend"
```

---

### Task 1.3: Update existing `npm test` to keep coverage green

- [ ] **Step 1: Verify nothing broke**

Run: `cd contracts && npm test`
Expected: existing 30+ tests in `PolyVault.test.ts` still PASS.

(no commit — just a verification step before moving on)

---

## Phase 2 — Frontend Scaffolding

### Task 2.1: Initialize the frontend project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.mjs`
- Create: `frontend/.gitignore`
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "polypredict-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test",
    "e2e:install": "playwright install --with-deps chromium"
  },
  "dependencies": {
    "@rainbow-me/rainbowkit": "^2.1.7",
    "@tanstack/react-query": "^5.59.16",
    "@tanstack/react-query-devtools": "^5.59.16",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "framer-motion": "^11.11.1",
    "lucide-react": "^0.453.0",
    "next": "14.2.15",
    "next-themes": "^0.3.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.13.0",
    "sonner": "^1.5.0",
    "tailwind-merge": "^2.5.4",
    "tailwindcss-animate": "^1.0.7",
    "viem": "^2.21.18",
    "wagmi": "^2.12.17",
    "zustand": "^4.5.5"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.1",
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-dropdown-menu": "^2.1.2",
    "@radix-ui/react-label": "^2.1.0",
    "@radix-ui/react-select": "^2.1.2",
    "@radix-ui/react-separator": "^1.1.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-tabs": "^1.1.1",
    "@radix-ui/react-toast": "^1.2.2",
    "@radix-ui/react-tooltip": "^1.1.3",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@types/node": "^22.7.4",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "autoprefixer": "^10.4.20",
    "eslint": "^8.57.1",
    "eslint-config-next": "14.2.15",
    "happy-dom": "^15.7.4",
    "msw": "^2.4.9",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.4.5",
    "vitest": "^2.1.2"
  },
  "engines": {
    "node": ">=20"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] },
    "target": "ES2022"
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `frontend/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Avoid SSR-pre-evaluating wagmi/RainbowKit (browser-only deps).
  transpilePackages: ["@rainbow-me/rainbowkit"],
  webpack: (config) => {
    // wagmi sometimes pulls "pino-pretty" through transitive deps; mark optional.
    config.externals.push("pino-pretty", "lokijs", "encoding");
    return config;
  },
};

export default nextConfig;
```

- [ ] **Step 4: Create `frontend/.gitignore`**

```
node_modules/
.next/
out/
.env.local
.env*.local
playwright-report/
test-results/
coverage/
*.tsbuildinfo
next-env.d.ts
```

- [ ] **Step 5: Create `frontend/.env.local.example`**

```env
# Backend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

# Hardhat localhost — chain id 31337
# These addresses are populated by `pnpm dev:contracts` (deploy-local-full.ts);
# the script writes contracts/exports/localhost.json which the frontend reads
# at runtime via lib/contracts.ts. The values below are fallback placeholders
# used only when the export file is missing (e.g. CI without a chain).
NEXT_PUBLIC_CHAIN_ID=31337
NEXT_PUBLIC_HARDHAT_RPC=http://127.0.0.1:8545
NEXT_PUBLIC_VAULT_ADDRESS=0x0000000000000000000000000000000000000000
NEXT_PUBLIC_USDC_ADDRESS=0x0000000000000000000000000000000000000000

# Optional: enables WalletConnect modal — leave blank to use injected only
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=

# Admin token for /admin page — must match backend ADMIN_API_KEY
NEXT_PUBLIC_ADMIN_API_KEY=dev_admin_key
```

- [ ] **Step 6: Initialize pnpm + install**

Run:
```bash
cd frontend && corepack enable && pnpm install
```

If `pnpm` isn't available, install with `npm i -g pnpm@9` first.

Expected: `frontend/node_modules/` and `frontend/pnpm-lock.yaml` created with no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/tsconfig.json frontend/next.config.mjs frontend/.gitignore frontend/.env.local.example frontend/pnpm-lock.yaml
git commit -m "feat(frontend): scaffold Next.js 14 + wagmi/rainbowkit deps"
```

---

### Task 2.2: Tailwind + design tokens

**Files:**
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`

- [ ] **Step 1: Create `frontend/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/hooks/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: { center: true, padding: "1rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
```

- [ ] **Step 2: Create `frontend/postcss.config.mjs`**

```javascript
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 3: Create `frontend/src/app/globals.css`**

The PRD §5.1 specifies indigo primary and explicit hex values. Map them to HSL variables:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222 47% 11%;
    --card: 220 14% 96%;
    --card-foreground: 222 47% 11%;
    --popover: 0 0% 100%;
    --popover-foreground: 222 47% 11%;
    --primary: 239 84% 67%;             /* indigo-500 #6366F1 */
    --primary-foreground: 0 0% 100%;
    --secondary: 220 14% 96%;
    --secondary-foreground: 222 47% 11%;
    --muted: 220 14% 96%;
    --muted-foreground: 215 16% 47%;
    --accent: 239 84% 67%;
    --accent-foreground: 0 0% 100%;
    --destructive: 0 84% 60%;           /* red-500 #EF4444 */
    --destructive-foreground: 0 0% 100%;
    --border: 220 13% 91%;
    --input: 220 13% 91%;
    --ring: 239 84% 67%;
    --success: 158 64% 40%;             /* emerald-500 #10B981 */
    --warning: 38 92% 50%;              /* amber-500 #F59E0B */
    --radius: 0.5rem;
  }
  .dark {
    --background: 240 10% 4%;            /* #0A0A0B */
    --foreground: 210 40% 98%;
    --card: 240 6% 9%;                   /* #141416 */
    --card-foreground: 210 40% 98%;
    --popover: 240 6% 9%;
    --popover-foreground: 210 40% 98%;
    --primary: 234 89% 74%;              /* indigo-400 #818CF8 */
    --primary-foreground: 240 10% 4%;
    --secondary: 240 6% 14%;
    --secondary-foreground: 210 40% 98%;
    --muted: 240 6% 14%;
    --muted-foreground: 218 11% 65%;
    --accent: 234 89% 74%;
    --accent-foreground: 240 10% 4%;
    --destructive: 0 91% 71%;            /* red-400 #F87171 */
    --destructive-foreground: 0 0% 100%;
    --border: 240 6% 16%;
    --input: 240 6% 16%;
    --ring: 234 89% 74%;
    --success: 158 64% 52%;              /* emerald-400 #34D399 */
    --warning: 38 96% 56%;               /* amber-400 #FBBF24 */
  }
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

- [ ] **Step 4: Create `frontend/components.json` (shadcn config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

- [ ] **Step 5: Create `frontend/src/lib/utils.ts`**

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 6: Verify Tailwind compiles**

Create a one-shot test page so we can prove styles flow. (Will be replaced in Task 3.) Run:
```bash
cd frontend && pnpm typecheck
```
Expected: no errors. (Tailwind itself is verified by the dev server in Task 3.)

- [ ] **Step 7: Commit**

```bash
git add frontend/tailwind.config.ts frontend/postcss.config.mjs frontend/src/app/globals.css frontend/components.json frontend/src/lib/utils.ts
git commit -m "feat(frontend): tailwind + design tokens (PRD §5)"
```

---

### Task 2.3: shadcn/ui base components (manual install)

**Files:**
- Create: `frontend/src/components/ui/{button,card,badge,table,tabs,dialog,sheet,tooltip,input,select,skeleton,separator,label,dropdown-menu}.tsx`

We install the shadcn primitives manually (no CLI roundtrip) — the source is well-known and stable. Each file follows the standard shadcn template using Radix primitives.

- [ ] **Step 1: Create `frontend/src/components/ui/button.tsx`**

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";
export { buttonVariants };
```

- [ ] **Step 2: Create the rest of the shadcn components**

Create each of these files using the canonical shadcn/ui template (https://ui.shadcn.com source). The *agent* implementing this task should write the standard template verbatim — they are deterministic, well-known, and unchanged across shadcn versions. Files to create (all in `frontend/src/components/ui/`):

- `card.tsx` (Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter)
- `badge.tsx` (Badge with `variant: default|secondary|destructive|outline`)
- `table.tsx` (Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption)
- `tabs.tsx` (Tabs, TabsList, TabsTrigger, TabsContent — wraps `@radix-ui/react-tabs`)
- `dialog.tsx` (wraps `@radix-ui/react-dialog`)
- `sheet.tsx` (wraps `@radix-ui/react-dialog` with side variants — for mobile nav)
- `tooltip.tsx` (wraps `@radix-ui/react-tooltip`)
- `input.tsx` (forwarded `<input>` with Tailwind classes)
- `select.tsx` (wraps `@radix-ui/react-select`)
- `skeleton.tsx` (`<div className="animate-pulse rounded-md bg-muted" />`)
- `separator.tsx` (wraps `@radix-ui/react-separator`)
- `label.tsx` (wraps `@radix-ui/react-label`)
- `dropdown-menu.tsx` (wraps `@radix-ui/react-dropdown-menu`)

Each file is ~50-100 lines and uses Radix primitives + the `cn()` helper. Source of truth: https://github.com/shadcn-ui/ui/tree/main/apps/www/registry/default/ui (use those exact file contents).

- [ ] **Step 3: Sanity-typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat(frontend): shadcn/ui primitives (button/card/badge/table/...)"
```

---

### Task 2.4: Wagmi + RainbowKit + chains config

**Files:**
- Create: `frontend/src/lib/chains.ts`
- Create: `frontend/src/lib/wagmi.ts`
- Create: `frontend/src/lib/contracts.ts`
- Create: `frontend/src/types/contracts.ts`
- Copy: `contracts/exports/abi/PolyVault.json` → `frontend/src/lib/abi/PolyVault.json`
- Copy: `contracts/exports/abi/MockUSDC.json` → `frontend/src/lib/abi/MockUSDC.json`

- [ ] **Step 1: Copy ABIs into the frontend**

Run:
```bash
mkdir -p frontend/src/lib/abi
cp contracts/exports/abi/PolyVault.json frontend/src/lib/abi/PolyVault.json
cp contracts/exports/abi/MockUSDC.json frontend/src/lib/abi/MockUSDC.json
```

- [ ] **Step 2: Create `frontend/src/lib/chains.ts`**

```typescript
import { defineChain } from "viem";
import { polygon, polygonAmoy } from "viem/chains";

// Hardhat default localhost — Anvil/Foundry use the same.
export const hardhatLocal = defineChain({
  id: 31337,
  name: "Hardhat Localhost",
  nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
  rpcUrls: {
    default: { http: ["http://127.0.0.1:8545"] },
    public: { http: ["http://127.0.0.1:8545"] },
  },
  testnet: true,
});

export const supportedChains = [hardhatLocal, polygonAmoy, polygon] as const;
```

- [ ] **Step 3: Create `frontend/src/lib/wagmi.ts`**

```typescript
"use client";
import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import { http } from "wagmi";
import { hardhatLocal, supportedChains } from "./chains";
import { polygon, polygonAmoy } from "viem/chains";

const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "polypredict-dev";

export const wagmiConfig = getDefaultConfig({
  appName: "PolyPredict AI",
  projectId,
  chains: supportedChains,
  transports: {
    [hardhatLocal.id]: http(process.env.NEXT_PUBLIC_HARDHAT_RPC || "http://127.0.0.1:8545"),
    [polygonAmoy.id]: http(),
    [polygon.id]: http(),
  },
  ssr: true,
});
```

- [ ] **Step 4: Create `frontend/src/lib/contracts.ts`**

```typescript
import polyVaultArtifact from "./abi/PolyVault.json";
import mockUsdcArtifact from "./abi/MockUSDC.json";

export const polyVaultAbi = polyVaultArtifact.abi;
export const mockUsdcAbi = mockUsdcArtifact.abi;

// Address registry. Per chain. Hardhat localhost addresses come from
// .env.local (overwritten by the dev script after deploying); Polygon Amoy
// + mainnet addresses are filled in once those deployments exist.
export const addresses: Record<number, { vault: `0x${string}`; usdc: `0x${string}` }> = {
  31337: {
    vault: (process.env.NEXT_PUBLIC_VAULT_ADDRESS || "0x0000000000000000000000000000000000000000") as `0x${string}`,
    usdc: (process.env.NEXT_PUBLIC_USDC_ADDRESS || "0x0000000000000000000000000000000000000000") as `0x${string}`,
  },
  80002: {
    vault: "0x0000000000000000000000000000000000000000",
    usdc: "0x0000000000000000000000000000000000000000", // fill once deployed
  },
  137: {
    vault: "0x0000000000000000000000000000000000000000",
    usdc: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", // native USDC on Polygon
  },
};

export function getContracts(chainId: number | undefined) {
  const cid = chainId ?? 31337;
  return addresses[cid] ?? addresses[31337];
}
```

- [ ] **Step 5: Create `frontend/src/types/contracts.ts`**

```typescript
// Strongly-typed shapes for vault read/write helpers.
import type { Address } from "viem";

export interface WithdrawalRequest {
  shares: bigint;
  requestTimestamp: bigint;
  pending: boolean;
}

export interface VaultStats {
  totalAssets: bigint;
  sharePrice: bigint;            // 1e18-scaled (one full share)
  withdrawalDelay: bigint;       // seconds
  minDeposit: bigint;            // 6-decimal USDC
  maxDeposit: bigint;            // 6-decimal USDC
}

export interface UserVaultPosition {
  shares: bigint;
  assets: bigint;                // shares-converted USDC value
  pendingWithdrawal: WithdrawalRequest | null;
  usdcBalance: bigint;
  usdcAllowance: bigint;
}

export type WriteState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "confirming"; hash: Address }
  | { status: "success"; hash: Address }
  | { status: "error"; message: string };
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && pnpm typecheck`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/chains.ts frontend/src/lib/wagmi.ts frontend/src/lib/contracts.ts frontend/src/lib/abi/ frontend/src/types/contracts.ts
git commit -m "feat(frontend): wagmi v2 + RainbowKit + Hardhat chain + contract registry"
```

---

### Task 2.5: API client + formatters

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/tests/unit/api.test.ts`
- Create: `frontend/src/tests/unit/format.test.ts`
- Create: `frontend/vitest.config.ts`

- [ ] **Step 1: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: [],
    include: ["src/tests/unit/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
});
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/tests/unit/format.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { formatUsdc, formatPercent, formatShares, shortAddress, formatCountdown } from "@/lib/format";

describe("formatUsdc", () => {
  it("formats 6-decimal USDC bigint to human string", () => {
    expect(formatUsdc(1_000_000n)).toBe("1.00");
    expect(formatUsdc(1_500_000n)).toBe("1.50");
    expect(formatUsdc(0n)).toBe("0.00");
    expect(formatUsdc(1_234_567_890n, 4)).toBe("1234.5679");
  });
});

describe("formatPercent", () => {
  it("formats 0..1 to integer percent by default", () => {
    expect(formatPercent(0.62)).toBe("62%");
    expect(formatPercent(0.7811)).toBe("78%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0.625, 1)).toBe("62.5%");
  });
});

describe("formatShares", () => {
  it("formats 18-decimal share bigints", () => {
    expect(formatShares(1_000_000_000_000_000_000n)).toBe("1.0000");
    expect(formatShares(0n)).toBe("0.0000");
  });
});

describe("shortAddress", () => {
  it("abbreviates a 0x-address", () => {
    expect(shortAddress("0x1234567890abcdef1234567890abcdef12345678")).toBe("0x1234...5678");
  });
});

describe("formatCountdown", () => {
  it("formats seconds-remaining as Hh Mm", () => {
    expect(formatCountdown(0)).toBe("now");
    expect(formatCountdown(60)).toBe("1m");
    expect(formatCountdown(3600)).toBe("1h 0m");
    expect(formatCountdown(60 * 60 * 24)).toBe("24h 0m");
    expect(formatCountdown(60 * 60 * 25 + 60 * 30)).toBe("25h 30m");
  });
});
```

Create `frontend/src/tests/unit/api.test.ts`:

```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

describe("api", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = realFetch;
  });

  it("GET prepends base URL and parses JSON", async () => {
    global.fetch = vi.fn(async (url) => {
      expect(url).toBe("http://localhost:8000/api/v1/markets/today");
      return new Response(JSON.stringify({ id: 1 }), { status: 200, headers: { "content-type": "application/json" } });
    }) as any;
    const result = await api.get<{ id: number }>("/markets/today");
    expect(result).toEqual({ id: 1 });
  });

  it("returns null on 404 by default", async () => {
    global.fetch = vi.fn(async () => new Response("not found", { status: 404 })) as any;
    const result = await api.get("/markets/today");
    expect(result).toBeNull();
  });

  it("throws ApiError on 500", async () => {
    global.fetch = vi.fn(async () => new Response("kaboom", { status: 500 })) as any;
    await expect(api.get("/markets/today")).rejects.toBeInstanceOf(ApiError);
  });

  it("POST attaches admin token when provided", async () => {
    let captured: any = null;
    global.fetch = vi.fn(async (_url, init) => {
      captured = init;
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
    }) as any;
    await api.post("/markets/scan", undefined, { adminToken: "secret" });
    expect(captured.headers.Authorization).toBe("Bearer secret");
    expect(captured.method).toBe("POST");
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && pnpm test`
Expected: FAIL — modules `@/lib/format` and `@/lib/api` not found.

- [ ] **Step 4: Implement `frontend/src/lib/format.ts`**

```typescript
export function formatUsdc(amount: bigint, decimals: number = 2): string {
  const divisor = 1_000_000n;
  const whole = amount / divisor;
  const frac = amount % divisor;
  // Pad fractional to 6 digits, then truncate to requested decimals.
  const fracStr = frac.toString().padStart(6, "0").slice(0, decimals);
  return `${whole.toString()}.${fracStr}`;
}

export function formatShares(shares: bigint, decimals: number = 4): string {
  const divisor = 10n ** 18n;
  const whole = shares / divisor;
  const frac = shares % divisor;
  const fracStr = frac.toString().padStart(18, "0").slice(0, decimals);
  return `${whole.toString()}.${fracStr}`;
}

export function formatPercent(ratio: number, decimals: number = 0): string {
  return `${(ratio * 100).toFixed(decimals)}%`;
}

export function shortAddress(addr: string): string {
  if (!addr || addr.length < 10) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

export function formatCountdown(seconds: number): string {
  if (seconds <= 0) return "now";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}
```

- [ ] **Step 5: Implement `frontend/src/lib/api.ts`**

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public body: string, public url: string) {
    super(`API ${status}: ${url}`);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  adminToken?: string;
  signal?: AbortSignal;
  /** When true, treat 404 as a real error rather than returning null. */
  throwOn404?: boolean;
}

async function request<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T | null> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.adminToken) headers.Authorization = `Bearer ${opts.adminToken}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  });

  if (res.status === 404 && !opts.throwOn404) return null;

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text, `${BASE_URL}${path}`);
  }

  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return null;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string, opts?: RequestOptions) => request<T>("GET", path, undefined, opts),
  post: <T,>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("POST", path, body, opts),
  delete: <T,>(path: string, opts?: RequestOptions) => request<T>("DELETE", path, undefined, opts),
};
```

- [ ] **Step 6: Create `frontend/src/types/api.ts` mirroring backend Pydantic schemas**

```typescript
export type ResolveStatus = "active" | "resolved" | "expired";
export type Resolution = "yes" | "no" | null;
export type Direction = "bullish" | "bearish" | "neutral";
export type RecommendedAction = "buy_yes" | "buy_no" | "skip";
export type StrategyAction = "buy_yes" | "buy_no" | "skip";
export type StrategyStatus = "skipped" | "pending" | "executing" | "active" | "closed" | "failed";
export type TradeSide = "yes" | "no";
export type TradeAction = "buy" | "sell";
export type TradeStatus = "pending" | "filled" | "partial" | "cancelled" | "failed";
export type CloseReason = "take_profit" | "stop_loss" | "pre_resolution" | "manual" | null;

export interface MarketResponse {
  id: number;
  polymarket_condition_id: string;
  polymarket_token_id: string;
  event_slug: string;
  question: string;
  price_threshold: number;
  scan_date: string;        // ISO date
  target_date: string;      // ISO date
  current_yes_price: string;
  current_no_price: string;
  selected_at: string;      // ISO datetime
  status: ResolveStatus;
  resolution: Resolution;
}

export interface PredictionResponse {
  id: number;
  market_id: number;
  predicted_probability: string;
  confidence: string;
  direction: Direction;
  key_factors: string[];
  risk_factors: string[];
  technical_analysis: string;
  sentiment_analysis: string;
  news_impact: string;
  onchain_analysis: string;
  reasoning: string;
  recommended_action: RecommendedAction;
  market_probability: string;
  edge: string;
  model_version: string;
  prompt_version: string;
  seed: number;
  tokens_used: number;
  latency_ms: number;
  created_at: string;
}

export interface PredictionDetailResponse extends PredictionResponse {
  raw_request: Record<string, unknown>;
  raw_response: Record<string, unknown>;
  data_snapshot: Record<string, unknown>;
}

export interface StrategyResponse {
  id: number;
  prediction_id: number;
  market_id: number;
  action: StrategyAction;
  side: TradeSide | null;
  position_size: string;
  entry_price: string;
  take_profit: string;
  stop_loss: string;
  kelly_fraction: string;
  edge: string;
  skip_reason: string;
  status: StrategyStatus;
  created_at: string;
  executed_at: string | null;
}

export interface TradeResponse {
  id: number;
  strategy_id: number;
  market_id: number;
  polymarket_order_id: string;
  side: TradeSide;
  action: TradeAction;
  amount: string;
  price: string;
  shares: string;
  status: TradeStatus;
  fee: string;
  pnl: string | null;
  close_reason: CloseReason;
  created_at: string;
  filled_at: string | null;
  closed_at: string | null;
}

export interface OverviewResponse {
  tvl: string;
  share_price: string;
  total_pnl: string;
  total_trades: number;
  win_rate: string;
  active_positions: number;
}

export interface DailyPnLResponse {
  day: string;       // ISO date
  pnl: string;
  trade_count: number;
}

export interface VaultSnapshotResponse {
  id: number;
  total_assets: string;
  share_price: string;
  tvl: string;
  depositor_count: number;
  deployed_amount: string;
  snapshot_at: string;
}

export interface SystemStatusResponse {
  paused: boolean;
  scheduler_running: boolean;
  monitor_running: boolean;
}

export interface LeaderboardEntryResponse {
  rank: number;
  wallet: string;
  deposited: string;
  current_value: string;
  profit: string;
  profit_pct: string;
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && pnpm test`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/format.ts frontend/src/types/api.ts frontend/src/tests/ frontend/vitest.config.ts
git commit -m "feat(frontend): API client + formatters + backend response types"
```

---

## Phase 3 — Frontend Providers + Global Layout

### Task 3.1: Providers (Web3 + Query + Theme)

**Files:**
- Create: `frontend/src/providers/Web3Provider.tsx`
- Create: `frontend/src/providers/QueryProvider.tsx`
- Create: `frontend/src/providers/ThemeProvider.tsx`

- [ ] **Step 1: Create `frontend/src/providers/Web3Provider.tsx`**

```tsx
"use client";
import * as React from "react";
import { WagmiProvider } from "wagmi";
import { RainbowKitProvider, darkTheme, lightTheme } from "@rainbow-me/rainbowkit";
import { useTheme } from "next-themes";
import "@rainbow-me/rainbowkit/styles.css";
import { wagmiConfig } from "@/lib/wagmi";

export function Web3Provider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  return (
    <WagmiProvider config={wagmiConfig}>
      <RainbowKitProvider
        theme={resolvedTheme === "dark" ? darkTheme() : lightTheme()}
        modalSize="compact"
      >
        {children}
      </RainbowKitProvider>
    </WagmiProvider>
  );
}
```

- [ ] **Step 2: Create `frontend/src/providers/QueryProvider.tsx`**

```tsx
"use client";
import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,           // 30s, per PRD §10
            refetchOnWindowFocus: false,
            retry: 2,
          },
        },
      })
  );
  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV === "development" ? <ReactQueryDevtools initialIsOpen={false} /> : null}
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: Create `frontend/src/providers/ThemeProvider.tsx`**

```tsx
"use client";
import * as React from "react";
import { ThemeProvider as NextThemesProvider, type ThemeProviderProps } from "next-themes";

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/providers/
git commit -m "feat(frontend): Web3 / Query / Theme providers"
```

---

### Task 3.2: Header + Footer + ThemeToggle

**Files:**
- Create: `frontend/src/components/layout/Header.tsx`
- Create: `frontend/src/components/layout/Footer.tsx`
- Create: `frontend/src/components/layout/ThemeToggle.tsx`

- [ ] **Step 1: Create `frontend/src/components/layout/Header.tsx`**

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { Sparkles } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/vault", label: "Vault" },
  { href: "/predictions", label: "Predictions" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/admin", label: "Admin" },
];

export function Header() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Sparkles className="h-5 w-5 text-primary" />
          <span>PolyPredict AI</span>
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "transition-colors hover:text-foreground",
                pathname === item.href ? "text-foreground font-medium" : "text-muted-foreground"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <ConnectButton chainStatus="icon" showBalance={false} accountStatus="address" />
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/layout/ThemeToggle.tsx`**

```tsx
"use client";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const next = resolvedTheme === "dark" ? "light" : "dark";
  return (
    <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={() => setTheme(next)}>
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="hidden h-4 w-4 dark:inline-block" />
    </Button>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/layout/Footer.tsx`**

```tsx
"use client";
import Link from "next/link";
import { useChainId } from "wagmi";
import { getContracts } from "@/lib/contracts";
import { shortAddress } from "@/lib/format";

export function Footer() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const explorerBase =
    chainId === 137 ? "https://polygonscan.com/address/" :
    chainId === 80002 ? "https://amoy.polygonscan.com/address/" :
    "";
  return (
    <footer className="border-t border-border py-6 text-sm text-muted-foreground">
      <div className="container flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-center gap-4">
          <Link href="https://polymarket.com" className="hover:text-foreground" target="_blank" rel="noopener">Polymarket</Link>
          <Link href="https://github.com" className="hover:text-foreground" target="_blank" rel="noopener">GitHub</Link>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          Vault:
          {explorerBase ? (
            <a href={`${explorerBase}${vault}`} target="_blank" rel="noopener" className="hover:text-foreground">{shortAddress(vault)}</a>
          ) : (
            <span>{shortAddress(vault)}</span>
          )}
        </div>
      </div>
    </footer>
  );
}
```

- [ ] **Step 4: Create root layout `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Toaster } from "sonner";

import "./globals.css";
import { ThemeProvider } from "@/providers/ThemeProvider";
import { QueryProvider } from "@/providers/QueryProvider";
import { Web3Provider } from "@/providers/Web3Provider";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "PolyPredict AI",
  description: "AI-driven Polymarket prediction vault on Polygon",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-background font-sans antialiased flex flex-col">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <QueryProvider>
            <Web3Provider>
              <Header />
              <main className="flex-1">{children}</main>
              <Footer />
              <Toaster richColors position="top-right" />
            </Web3Provider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Create a placeholder home page so the dev server boots**

Create `frontend/src/app/page.tsx`:

```tsx
export default function Page() {
  return (
    <div className="container py-12">
      <h1 className="text-3xl font-bold">PolyPredict AI</h1>
      <p className="mt-2 text-muted-foreground">Dashboard coming online…</p>
    </div>
  );
}
```

- [ ] **Step 6: Boot the dev server and verify**

Run (in a separate shell — use `run_in_background`):
```bash
cd frontend && pnpm dev
```
Wait ~5s; then `curl -s http://localhost:3000 | grep PolyPredict` — expect to see the title in the HTML.

Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/ frontend/src/app/layout.tsx frontend/src/app/page.tsx
git commit -m "feat(frontend): root layout + Header + Footer + ThemeToggle"
```

---

## Phase 4 — Frontend Hooks (TDD where deterministic)

For wagmi hooks (`useVault`, `useUSDC`, `useVaultWrite`), TDD with full mocking is heavyweight; we lean on Playwright E2E in Phase 7. For pure-data hooks (`useStats`, `usePredictions`), we test against MSW (Mock Service Worker).

### Task 4.1: `useVault` — read-only vault contract reads

**Files:**
- Create: `frontend/src/hooks/useVault.ts`

- [ ] **Step 1: Implement the hook**

```typescript
"use client";
import { useReadContract, useChainId } from "wagmi";
import { polyVaultAbi, getContracts } from "@/lib/contracts";
import type { Address } from "viem";

const REFETCH_INTERVAL = 30_000; // 30s per PRD §4.4

export function useVaultStats() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const opts = { abi: polyVaultAbi, address: vault as Address, query: { refetchInterval: REFETCH_INTERVAL } };

  const totalAssets = useReadContract({ ...opts, functionName: "totalAssets" });
  const withdrawalDelay = useReadContract({ ...opts, functionName: "withdrawalDelay" });
  const minDeposit = useReadContract({ ...opts, functionName: "minDeposit" });
  const maxDeposit = useReadContract({ ...opts, functionName: "maxDeposit" });
  const sharePrice = useReadContract({
    ...opts,
    functionName: "convertToAssets",
    args: [10n ** 18n], // value of 1 share
  });
  const strategyDebt = useReadContract({ ...opts, functionName: "strategyDebt" });
  const totalSupply = useReadContract({ ...opts, functionName: "totalSupply" });

  return {
    totalAssets: (totalAssets.data as bigint | undefined) ?? 0n,
    sharePrice: (sharePrice.data as bigint | undefined) ?? 10n ** 18n, // 1.0 default
    withdrawalDelay: (withdrawalDelay.data as bigint | undefined) ?? 0n,
    minDeposit: (minDeposit.data as bigint | undefined) ?? 0n,
    maxDeposit: (maxDeposit.data as bigint | undefined) ?? 0n,
    strategyDebt: (strategyDebt.data as bigint | undefined) ?? 0n,
    totalSupply: (totalSupply.data as bigint | undefined) ?? 0n,
    isLoading: totalAssets.isLoading || sharePrice.isLoading,
    refetchAll: () => {
      totalAssets.refetch();
      sharePrice.refetch();
      strategyDebt.refetch();
      totalSupply.refetch();
    },
  };
}

export function useUserVaultPosition(user: Address | undefined) {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const enabled = !!user;
  const opts = { abi: polyVaultAbi, address: vault as Address };

  const shares = useReadContract({
    ...opts, functionName: "balanceOf", args: user ? [user] : undefined,
    query: { enabled, refetchInterval: REFETCH_INTERVAL },
  });
  const sharesValue = useReadContract({
    ...opts, functionName: "convertToAssets",
    args: shares.data !== undefined ? [shares.data as bigint] : undefined,
    query: { enabled: enabled && shares.data !== undefined },
  });
  const pending = useReadContract({
    ...opts, functionName: "getWithdrawalRequest", args: user ? [user] : undefined,
    query: { enabled, refetchInterval: REFETCH_INTERVAL },
  });

  return {
    shares: (shares.data as bigint | undefined) ?? 0n,
    assets: (sharesValue.data as bigint | undefined) ?? 0n,
    pending: pending.data as { shares: bigint; requestTimestamp: bigint; pending: boolean } | undefined,
    isLoading: shares.isLoading || pending.isLoading,
    refetch: () => { shares.refetch(); sharesValue.refetch(); pending.refetch(); },
  };
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useVault.ts
git commit -m "feat(frontend): useVaultStats + useUserVaultPosition hooks"
```

---

### Task 4.2: `useUSDC` — balance + allowance

**Files:**
- Create: `frontend/src/hooks/useUSDC.ts`

- [ ] **Step 1: Implement**

```typescript
"use client";
import { useChainId, useReadContract } from "wagmi";
import { mockUsdcAbi, getContracts } from "@/lib/contracts";
import type { Address } from "viem";

export function useUSDC(user: Address | undefined) {
  const chainId = useChainId();
  const { vault, usdc } = getContracts(chainId);
  const enabled = !!user;
  const opts = { abi: mockUsdcAbi, address: usdc as Address };

  const balance = useReadContract({
    ...opts, functionName: "balanceOf", args: user ? [user] : undefined,
    query: { enabled, refetchInterval: 30_000 },
  });
  const allowance = useReadContract({
    ...opts, functionName: "allowance", args: user ? [user, vault as Address] : undefined,
    query: { enabled, refetchInterval: 15_000 },
  });

  return {
    balance: (balance.data as bigint | undefined) ?? 0n,
    allowance: (allowance.data as bigint | undefined) ?? 0n,
    isLoading: balance.isLoading || allowance.isLoading,
    refetch: () => { balance.refetch(); allowance.refetch(); },
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useUSDC.ts
git commit -m "feat(frontend): useUSDC hook (balance + allowance)"
```

---

### Task 4.3: `useVaultWrite` — deposit / withdraw flow

**Files:**
- Create: `frontend/src/hooks/useVaultWrite.ts`

- [ ] **Step 1: Implement**

```typescript
"use client";
import * as React from "react";
import { useAccount, useChainId, useWaitForTransactionReceipt, useWriteContract } from "wagmi";
import { toast } from "sonner";
import { polyVaultAbi, mockUsdcAbi, getContracts } from "@/lib/contracts";
import type { Address } from "viem";

type WriteHelpers = ReturnType<typeof useWriteContract>;

function useTracked(action: string, helpers: WriteHelpers) {
  const wait = useWaitForTransactionReceipt({ hash: helpers.data });
  React.useEffect(() => {
    if (wait.isSuccess && helpers.data) toast.success(`${action} confirmed`, { description: helpers.data });
    if (helpers.isError) toast.error(`${action} failed`, { description: (helpers.error as Error)?.message });
  }, [wait.isSuccess, helpers.isError, helpers.data, action, helpers.error]);
  return {
    write: helpers.writeContract,
    hash: helpers.data,
    isPending: helpers.isPending,
    isConfirming: wait.isLoading,
    isSuccess: wait.isSuccess,
  };
}

export function useApproveUsdc() {
  const chainId = useChainId();
  const { vault, usdc } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Approve", w);
  return {
    ...tracked,
    approve: (amount: bigint) =>
      w.writeContract({ abi: mockUsdcAbi, address: usdc as Address, functionName: "approve", args: [vault as Address, amount] }),
  };
}

export function useDepositUsdc() {
  const { address } = useAccount();
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Deposit", w);
  return {
    ...tracked,
    deposit: (amount: bigint) => {
      if (!address) return;
      w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "deposit", args: [amount, address] });
    },
  };
}

export function useRequestWithdraw() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Request withdraw", w);
  return {
    ...tracked,
    request: (shares: bigint) =>
      w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "requestWithdraw", args: [shares] }),
  };
}

export function useCancelWithdraw() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Cancel withdraw", w);
  return {
    ...tracked,
    cancel: () => w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "cancelWithdraw", args: [] }),
  };
}

export function useExecuteWithdraw() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Execute withdraw", w);
  return {
    ...tracked,
    execute: () => w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "executeWithdraw", args: [] }),
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useVaultWrite.ts
git commit -m "feat(frontend): vault write hooks (approve/deposit/request/cancel/execute)"
```

---

### Task 4.4: Backend-data hooks (TanStack Query wrappers)

**Files:**
- Create: `frontend/src/hooks/useMarkets.ts`
- Create: `frontend/src/hooks/usePredictions.ts`
- Create: `frontend/src/hooks/useStrategies.ts`
- Create: `frontend/src/hooks/useTrades.ts`
- Create: `frontend/src/hooks/useStats.ts`
- Create: `frontend/src/hooks/useSystem.ts`
- Create: `frontend/src/store/admin.ts`

- [ ] **Step 1: Create the admin token zustand store**

`frontend/src/store/admin.ts`:

```typescript
"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AdminState {
  token: string;
  setToken: (token: string) => void;
  clear: () => void;
}

export const useAdminStore = create<AdminState>()(
  persist(
    (set) => ({
      token: process.env.NEXT_PUBLIC_ADMIN_API_KEY || "",
      setToken: (token) => set({ token }),
      clear: () => set({ token: "" }),
    }),
    { name: "polypredict-admin" }
  )
);
```

- [ ] **Step 2: `frontend/src/hooks/useMarkets.ts`**

```typescript
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { MarketResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useTodayMarket() {
  return useQuery({
    queryKey: ["markets", "today"],
    queryFn: () => api.get<MarketResponse>("/markets/today"),
  });
}

export function useScanMarket() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<MarketResponse>("/markets/scan", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["markets"] }),
  });
}
```

- [ ] **Step 3: `frontend/src/hooks/usePredictions.ts`**

```typescript
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PredictionResponse, PredictionDetailResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useTodayPrediction() {
  return useQuery({
    queryKey: ["predictions", "today"],
    queryFn: () => api.get<PredictionResponse>("/predictions/today"),
    refetchInterval: 15_000,
  });
}

export function usePredictionHistory() {
  return useQuery({
    queryKey: ["predictions", "history"],
    queryFn: () => api.get<PredictionResponse[]>("/predictions/history"),
  });
}

export function usePredictionDetail(id: number | undefined) {
  return useQuery({
    queryKey: ["predictions", "detail", id],
    queryFn: () => api.get<PredictionDetailResponse>(`/predictions/${id}`),
    enabled: id !== undefined,
  });
}

export function useTriggerPrediction() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<PredictionResponse>("/predictions/trigger", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["predictions"] }),
  });
}
```

- [ ] **Step 4: `frontend/src/hooks/useStrategies.ts`**

```typescript
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StrategyResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useActiveStrategies() {
  return useQuery({
    queryKey: ["strategies", "active"],
    queryFn: () => api.get<StrategyResponse[]>("/strategies/active"),
    refetchInterval: 15_000,
  });
}

export function useStrategyHistory() {
  return useQuery({
    queryKey: ["strategies", "history"],
    queryFn: () => api.get<StrategyResponse[]>("/strategies/history"),
  });
}

export function useGenerateStrategy() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<StrategyResponse>("/strategies/generate", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}
```

- [ ] **Step 5: `frontend/src/hooks/useTrades.ts`**

```typescript
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TradeResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useActiveTrades() {
  return useQuery({
    queryKey: ["trades", "active"],
    queryFn: () => api.get<TradeResponse[]>("/trades/active"),
    refetchInterval: 15_000,
  });
}

export function useTradeHistory(limit?: number) {
  return useQuery({
    queryKey: ["trades", "history", limit],
    queryFn: async () => {
      const all = await api.get<TradeResponse[]>("/trades/history");
      if (!all) return [];
      return limit ? all.slice(0, limit) : all;
    },
  });
}

export function useExecuteTrade() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<TradeResponse>("/trades/execute", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trades"] }),
  });
}
```

- [ ] **Step 6: `frontend/src/hooks/useStats.ts`**

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OverviewResponse, DailyPnLResponse, VaultSnapshotResponse, LeaderboardEntryResponse } from "@/types/api";

export function useOverview() {
  return useQuery({
    queryKey: ["stats", "overview"],
    queryFn: () => api.get<OverviewResponse>("/stats/overview"),
    refetchInterval: 30_000,
  });
}

export function useDailyPnL(days: number = 30) {
  return useQuery({
    queryKey: ["stats", "daily", days],
    queryFn: () => api.get<DailyPnLResponse[]>(`/stats/daily?days=${days}`),
  });
}

export function useVaultHistory(limit: number = 168) {
  return useQuery({
    queryKey: ["stats", "vault", limit],
    queryFn: () => api.get<VaultSnapshotResponse[]>(`/stats/vault?limit=${limit}`),
  });
}

export function useLeaderboard() {
  return useQuery({
    queryKey: ["stats", "leaderboard"],
    queryFn: () => api.get<LeaderboardEntryResponse[]>("/stats/leaderboard"),
  });
}
```

- [ ] **Step 7: `frontend/src/hooks/useSystem.ts`**

```typescript
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SystemStatusResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: () => api.get<SystemStatusResponse>("/system/status"),
    refetchInterval: 15_000,
  });
}

export function usePauseSystem() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<void>("/system/pause", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["system"] }),
  });
}

export function useResumeSystem() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<void>("/system/resume", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["system"] }),
  });
}
```

- [ ] **Step 8: Typecheck + commit**

Run: `cd frontend && pnpm typecheck`
Expected: PASS.

```bash
git add frontend/src/hooks/ frontend/src/store/
git commit -m "feat(frontend): TanStack Query hooks for backend data"
```

---

### Task 4.5: `useBTCPrice` — Binance WebSocket BTC price

**Files:**
- Create: `frontend/src/hooks/useBTCPrice.ts`

- [ ] **Step 1: Implement**

```typescript
"use client";
import * as React from "react";

interface BinanceTicker {
  s: string;       // symbol
  c: string;       // last close price
  P: string;       // 24h change percent
}

const WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@ticker";

export function useBTCPrice() {
  const [price, setPrice] = React.useState<number | null>(null);
  const [change, setChange] = React.useState<number | null>(null);
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;
    function open() {
      if (cancelled) return;
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const t = JSON.parse(ev.data) as BinanceTicker;
          setPrice(parseFloat(t.c));
          setChange(parseFloat(t.P));
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(open, 2_000); // auto-reconnect
      };
      ws.onerror = () => ws?.close();
    }
    open();
    return () => { cancelled = true; ws?.close(); };
  }, []);

  return { price, change, connected };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useBTCPrice.ts
git commit -m "feat(frontend): useBTCPrice — Binance WS live ticker"
```

---

## Phase 5 — Frontend Pages (parallelizable across subagents)

> Subagent dispatch: Tasks 5.1, 5.2, 5.3, 5.4, 5.5, 5.6 are independent. After Phase 4 lands, dispatch them in parallel.

### Task 5.1: Dashboard `/` (page + 4 components)

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Create: `frontend/src/components/dashboard/StatsCards.tsx`
- Create: `frontend/src/components/dashboard/TodayPrediction.tsx`
- Create: `frontend/src/components/dashboard/PnLChart.tsx`
- Create: `frontend/src/components/dashboard/RecentTrades.tsx`

- [ ] **Step 1: `StatsCards.tsx`**

```tsx
"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOverview } from "@/hooks/useStats";
import { formatUsdc, formatPercent } from "@/lib/format";
import { TrendingUp, TrendingDown, Wallet, Target, DollarSign } from "lucide-react";

export function StatsCards() {
  const { data, isLoading } = useOverview();
  const tvl = data ? BigInt(data.tvl.split(".")[0] || "0") * 1_000_000n + BigInt((data.tvl.split(".")[1] || "0").padEnd(6, "0").slice(0, 6)) : 0n;
  const sharePrice = data ? Number(data.share_price) : 1;
  const pnl = data ? Number(data.total_pnl) : 0;
  const winRate = data ? Number(data.win_rate) : 0;
  const stat = (label: string, value: React.ReactNode, icon: React.ReactNode) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        {isLoading ? <Skeleton className="h-8 w-24" /> : <div className="text-2xl font-bold">{value}</div>}
      </CardContent>
    </Card>
  );
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stat("TVL", `$${formatUsdc(tvl, 0)}`, <Wallet className="h-4 w-4 text-muted-foreground" />)}
      {stat("Win rate", formatPercent(winRate), <Target className="h-4 w-4 text-muted-foreground" />)}
      {stat("Total PnL",
        <span className={pnl >= 0 ? "text-success" : "text-destructive"}>
          {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)} USDC
        </span>,
        pnl >= 0 ? <TrendingUp className="h-4 w-4 text-success" /> : <TrendingDown className="h-4 w-4 text-destructive" />)}
      {stat("Share price", `$${sharePrice.toFixed(4)}`, <DollarSign className="h-4 w-4 text-muted-foreground" />)}
    </div>
  );
}
```

- [ ] **Step 2: `TodayPrediction.tsx`**

```tsx
"use client";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useTodayMarket } from "@/hooks/useMarkets";
import { useTodayPrediction } from "@/hooks/usePredictions";
import { useActiveStrategies } from "@/hooks/useStrategies";
import { formatPercent } from "@/lib/format";
import { ArrowRight, Sparkles } from "lucide-react";

export function TodayPrediction() {
  const market = useTodayMarket();
  const prediction = useTodayPrediction();
  const strategies = useActiveStrategies();
  const strategy = strategies.data?.find((s) => s.market_id === market.data?.id);

  if (market.isLoading || prediction.isLoading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-48" /></CardHeader>
        <CardContent><Skeleton className="h-32 w-full" /></CardContent>
      </Card>
    );
  }
  if (!market.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today's prediction</CardTitle>
          <CardDescription>No market scanned yet today.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Run a scan from the Admin page or wait for the 00:00 UTC scheduler.
        </CardContent>
      </Card>
    );
  }
  const aiProb = prediction.data ? Number(prediction.data.predicted_probability) : null;
  const mktProb = market.data ? Number(market.data.current_yes_price) : null;
  const conf = prediction.data ? Number(prediction.data.confidence) : null;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary" /> Today's prediction</CardTitle>
            <CardDescription className="mt-1">{market.data.question}</CardDescription>
          </div>
          {strategy && (
            <Badge variant={strategy.action === "skip" ? "outline" : "default"}>
              {strategy.action.toUpperCase()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Polymarket Yes" value={mktProb !== null ? formatPercent(mktProb) : "—"} />
          <Stat label="AI predicted" value={aiProb !== null ? formatPercent(aiProb) : "—"} />
          <Stat label="Confidence" value={conf !== null ? formatPercent(conf) : "—"} />
          <Stat label="Edge" value={prediction.data ? `${(Number(prediction.data.edge) * 100).toFixed(1)}%` : "—"} />
        </div>
        {prediction.data?.recommended_action && prediction.data.recommended_action !== "skip" && (
          <p className="text-sm text-muted-foreground">{prediction.data.reasoning}</p>
        )}
        <Button asChild variant="outline" size="sm">
          <Link href={prediction.data ? `/predictions/${prediction.data.id}` : "/predictions"}>
            Full analysis <ArrowRight className="ml-1 h-3 w-3" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </div>
  );
}
```

- [ ] **Step 3: `PnLChart.tsx`**

```tsx
"use client";
import { useDailyPnL } from "@/hooks/useStats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export function PnLChart() {
  const { data, isLoading } = useDailyPnL(30);
  const series = (data ?? []).map((d) => ({ day: d.day.slice(5), pnl: Number(d.pnl) }));
  // running cumulative PnL
  let cum = 0;
  const cumSeries = series.map((s) => ({ day: s.day, cum: (cum += s.pnl) }));
  return (
    <Card className="col-span-2">
      <CardHeader><CardTitle>30-day PnL</CardTitle></CardHeader>
      <CardContent className="h-64">
        {isLoading ? <Skeleton className="h-full w-full" /> : (
          cumSeries.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No trades yet</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={cumSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                <Line type="monotone" dataKey="cum" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: `RecentTrades.tsx`**

```tsx
"use client";
import Link from "next/link";
import { useTradeHistory } from "@/hooks/useTrades";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2, XCircle, Clock } from "lucide-react";

export function RecentTrades() {
  const { data, isLoading } = useTradeHistory(10);
  return (
    <Card>
      <CardHeader><CardTitle>Recent trades</CardTitle></CardHeader>
      <CardContent>
        {isLoading ? <Skeleton className="h-48 w-full" /> : (
          (!data || data.length === 0) ? (
            <p className="text-sm text-muted-foreground">No trades yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.map((t) => {
                const pnl = t.pnl !== null ? Number(t.pnl) : null;
                const icon = pnl === null ? <Clock className="h-4 w-4 text-muted-foreground" /> :
                             pnl > 0 ? <CheckCircle2 className="h-4 w-4 text-success" /> :
                             <XCircle className="h-4 w-4 text-destructive" />;
                return (
                  <li key={t.id} className="flex items-center justify-between border-b border-border/50 pb-2">
                    <Link href={`/predictions`} className="flex items-center gap-2 hover:text-primary">
                      {icon}
                      <span className="font-mono text-xs">{t.created_at.slice(0, 10)}</span>
                      <span className="uppercase">{t.side}</span>
                    </Link>
                    <span className={pnl === null ? "" : pnl >= 0 ? "text-success" : "text-destructive"}>
                      {pnl === null ? "open" : `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          )
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: `frontend/src/app/page.tsx`**

```tsx
import { StatsCards } from "@/components/dashboard/StatsCards";
import { TodayPrediction } from "@/components/dashboard/TodayPrediction";
import { PnLChart } from "@/components/dashboard/PnLChart";
import { RecentTrades } from "@/components/dashboard/RecentTrades";

export default function DashboardPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">AI-driven Polymarket prediction vault</p>
      </header>
      <StatsCards />
      <TodayPrediction />
      <div className="grid gap-4 md:grid-cols-3">
        <PnLChart />
        <RecentTrades />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Boot dev server and inspect**

Run `pnpm dev` (background); fetch `http://localhost:3000` — should load with skeleton state (no backend running yet). Stop server.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/page.tsx frontend/src/components/dashboard/
git commit -m "feat(frontend): dashboard page (StatsCards + TodayPrediction + PnLChart + RecentTrades)"
```

---

### Task 5.2: Vault page `/vault`

**Files:**
- Create: `frontend/src/app/vault/page.tsx`
- Create: `frontend/src/components/vault/VaultInfo.tsx`
- Create: `frontend/src/components/vault/DepositForm.tsx`
- Create: `frontend/src/components/vault/WithdrawForm.tsx`
- Create: `frontend/src/components/vault/PendingWithdrawals.tsx`
- Create: `frontend/src/components/vault/SharePriceChart.tsx`

- [ ] **Step 1: `VaultInfo.tsx`**

```tsx
"use client";
import { useAccount } from "wagmi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useVaultStats, useUserVaultPosition } from "@/hooks/useVault";
import { formatUsdc, formatShares } from "@/lib/format";

export function VaultInfo() {
  const { address } = useAccount();
  const stats = useVaultStats();
  const pos = useUserVaultPosition(address);
  const profit = pos.assets - pos.shares; // a rough proxy when share price > 1
  return (
    <Card>
      <CardHeader><CardTitle>Vault</CardTitle></CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-3">
        <Stat label="TVL" value={`$${formatUsdc(stats.totalAssets)}`} />
        <Stat label="Share price" value={`$${formatUsdc(stats.sharePrice / 10n ** 12n, 6)}`} />
        <Stat label="Total supply" value={formatShares(stats.totalSupply)} />
        <Stat label="Your shares" value={formatShares(pos.shares)} />
        <Stat label="Your value" value={`$${formatUsdc(pos.assets)}`} />
        <Stat label="Approx PnL" value={`${profit >= 0n ? "+" : ""}$${formatUsdc(profit)}`} />
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-xl font-semibold mt-1 font-mono">{value}</div>
    </div>
  );
}
```

- [ ] **Step 2: `DepositForm.tsx`**

```tsx
"use client";
import * as React from "react";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApproveUsdc, useDepositUsdc } from "@/hooks/useVaultWrite";
import { useUSDC } from "@/hooks/useUSDC";
import { useVaultStats } from "@/hooks/useVault";
import { formatUsdc } from "@/lib/format";

const SIX = 1_000_000n;

export function DepositForm() {
  const { address } = useAccount();
  const usdc = useUSDC(address);
  const stats = useVaultStats();
  const approve = useApproveUsdc();
  const deposit = useDepositUsdc();
  const [amountStr, setAmountStr] = React.useState("100");

  const amount = React.useMemo(() => {
    const n = parseFloat(amountStr);
    if (isNaN(n) || n <= 0) return 0n;
    return BigInt(Math.floor(n * 1_000_000));
  }, [amountStr]);

  const previewShares = stats.sharePrice > 0n ? (amount * 10n ** 18n) / stats.sharePrice : 0n;
  const needsApproval = amount > 0n && usdc.allowance < amount;
  const exceedsBalance = amount > usdc.balance;

  return (
    <Card>
      <CardHeader><CardTitle>Deposit</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="dep-amt">Amount (USDC)</Label>
          <Input id="dep-amt" type="number" min={1} value={amountStr} onChange={(e) => setAmountStr(e.target.value)} />
          <div className="text-xs text-muted-foreground">
            Wallet: {formatUsdc(usdc.balance)} USDC · You will receive ~{formatUsdc(previewShares / 10n ** 12n, 6)} pvUSDC
          </div>
          {exceedsBalance && <p className="text-xs text-destructive">Insufficient USDC balance</p>}
        </div>
        <div className="flex flex-col gap-2">
          {needsApproval ? (
            <Button onClick={() => approve.approve(amount)} disabled={approve.isPending || approve.isConfirming || amount === 0n}>
              {approve.isConfirming ? "Confirming…" : approve.isPending ? "Waiting wallet…" : "Approve USDC"}
            </Button>
          ) : (
            <Button onClick={() => deposit.deposit(amount)} disabled={deposit.isPending || deposit.isConfirming || amount === 0n || exceedsBalance}>
              {deposit.isConfirming ? "Confirming…" : deposit.isPending ? "Waiting wallet…" : "Deposit"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: `WithdrawForm.tsx`**

```tsx
"use client";
import * as React from "react";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUserVaultPosition, useVaultStats } from "@/hooks/useVault";
import { useRequestWithdraw } from "@/hooks/useVaultWrite";
import { formatShares, formatUsdc, formatCountdown } from "@/lib/format";

export function WithdrawForm() {
  const { address } = useAccount();
  const pos = useUserVaultPosition(address);
  const stats = useVaultStats();
  const request = useRequestWithdraw();
  const [shareStr, setShareStr] = React.useState("");

  const shares = React.useMemo(() => {
    const n = parseFloat(shareStr);
    if (isNaN(n) || n <= 0) return 0n;
    return BigInt(Math.floor(n * 1e18));
  }, [shareStr]);

  const exceedsBalance = shares > pos.shares;
  const previewAssets = stats.sharePrice > 0n ? (shares * stats.sharePrice) / 10n ** 18n : 0n;

  return (
    <Card>
      <CardHeader><CardTitle>Request withdrawal</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="wd-shares">Shares (pvUSDC)</Label>
          <Input id="wd-shares" type="number" min={0} step="0.0001" value={shareStr} onChange={(e) => setShareStr(e.target.value)} />
          <div className="text-xs text-muted-foreground">
            Balance: {formatShares(pos.shares)} pvUSDC · You will receive ~${formatUsdc(previewAssets)} after {formatCountdown(Number(stats.withdrawalDelay))}
          </div>
          {exceedsBalance && <p className="text-xs text-destructive">Insufficient share balance</p>}
        </div>
        <Button
          variant="outline"
          onClick={() => request.request(shares)}
          disabled={request.isPending || request.isConfirming || shares === 0n || exceedsBalance || (pos.pending?.pending ?? false)}
        >
          {request.isConfirming ? "Confirming…" : request.isPending ? "Waiting wallet…" : pos.pending?.pending ? "Pending request exists" : "Request withdrawal"}
        </Button>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: `PendingWithdrawals.tsx`**

```tsx
"use client";
import * as React from "react";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useUserVaultPosition, useVaultStats } from "@/hooks/useVault";
import { useCancelWithdraw, useExecuteWithdraw } from "@/hooks/useVaultWrite";
import { formatShares, formatUsdc, formatCountdown } from "@/lib/format";

export function PendingWithdrawals() {
  const { address } = useAccount();
  const pos = useUserVaultPosition(address);
  const stats = useVaultStats();
  const cancel = useCancelWithdraw();
  const exec = useExecuteWithdraw();

  // Re-render once a second to update countdown
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setTick((x) => x + 1), 1_000);
    return () => clearInterval(id);
  }, []);

  if (!pos.pending?.pending) {
    return (
      <Card>
        <CardHeader><CardTitle>Pending withdrawals</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">No pending withdrawals.</CardContent>
      </Card>
    );
  }
  const ready = Number(pos.pending.requestTimestamp) + Number(stats.withdrawalDelay);
  const now = Math.floor(Date.now() / 1000);
  const remaining = Math.max(0, ready - now);
  const previewAssets = stats.sharePrice > 0n ? (pos.pending.shares * stats.sharePrice) / 10n ** 18n : 0n;

  return (
    <Card>
      <CardHeader><CardTitle>Pending withdrawals</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div>
          <strong>{formatShares(pos.pending.shares)} pvUSDC</strong> → ~${formatUsdc(previewAssets)}
        </div>
        <div>
          Requested at <span className="font-mono">{new Date(Number(pos.pending.requestTimestamp) * 1000).toLocaleString()}</span>
        </div>
        <div>
          {remaining > 0 ? `Available in ${formatCountdown(remaining)}` : "Available now"}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => cancel.cancel()} disabled={cancel.isPending || cancel.isConfirming}>
            {cancel.isConfirming ? "Cancelling…" : "Cancel"}
          </Button>
          <Button size="sm" onClick={() => exec.execute()} disabled={remaining > 0 || exec.isPending || exec.isConfirming}>
            {exec.isConfirming ? "Confirming…" : "Execute"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: `SharePriceChart.tsx`**

```tsx
"use client";
import { useVaultHistory } from "@/hooks/useStats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export function SharePriceChart() {
  const { data, isLoading } = useVaultHistory(168);
  const series = (data ?? []).slice().reverse().map((s) => ({
    t: s.snapshot_at.slice(5, 10),
    price: Number(s.share_price),
  }));
  return (
    <Card>
      <CardHeader><CardTitle>Share price history</CardTitle></CardHeader>
      <CardContent className="h-64">
        {isLoading ? <Skeleton className="h-full w-full" /> : (
          series.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No snapshots yet</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="t" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                <Line type="monotone" dataKey="price" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: `frontend/src/app/vault/page.tsx`**

```tsx
"use client";
import { useAccount } from "wagmi";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { VaultInfo } from "@/components/vault/VaultInfo";
import { DepositForm } from "@/components/vault/DepositForm";
import { WithdrawForm } from "@/components/vault/WithdrawForm";
import { PendingWithdrawals } from "@/components/vault/PendingWithdrawals";
import { SharePriceChart } from "@/components/vault/SharePriceChart";

export default function VaultPage() {
  const { isConnected } = useAccount();
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Vault</h1>
        <p className="text-muted-foreground">Deposit USDC to mint pvUSDC; withdrawals require a 24h delay.</p>
      </header>
      {!isConnected ? (
        <div className="rounded-lg border border-dashed p-8 text-center space-y-3">
          <p className="text-muted-foreground">Connect a wallet to deposit or withdraw.</p>
          <div className="flex justify-center"><ConnectButton /></div>
        </div>
      ) : (
        <>
          <VaultInfo />
          <div className="grid gap-4 md:grid-cols-2">
            <DepositForm />
            <WithdrawForm />
          </div>
          <PendingWithdrawals />
          <SharePriceChart />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Typecheck + commit**

Run: `cd frontend && pnpm typecheck`
Expected: PASS.

```bash
git add frontend/src/app/vault frontend/src/components/vault/
git commit -m "feat(frontend): /vault page (info + deposit/withdraw/pending/share-price chart)"
```

---

### Task 5.3: Predictions list `/predictions`

**Files:**
- Create: `frontend/src/app/predictions/page.tsx`
- Create: `frontend/src/components/predictions/PredictionList.tsx`
- Create: `frontend/src/components/predictions/PredictionCard.tsx`

- [ ] **Step 1: `PredictionCard.tsx`**

```tsx
"use client";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { PredictionResponse, MarketResponse } from "@/types/api";
import { formatPercent } from "@/lib/format";

export function PredictionCard({
  prediction, market,
}: { prediction: PredictionResponse; market?: MarketResponse }) {
  const aiProb = Number(prediction.predicted_probability);
  const mktProb = Number(prediction.market_probability);
  const edge = Number(prediction.edge);
  const edgeColor = edge > 0 ? "text-success" : edge < 0 ? "text-destructive" : "text-muted-foreground";
  return (
    <Card asChild className="hover:bg-muted/30 transition-colors">
      <Link href={`/predictions/${prediction.id}`}>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 pb-3">
          <div>
            <div className="text-xs text-muted-foreground font-mono">{prediction.created_at.slice(0, 10)}</div>
            <h3 className="font-medium mt-1">{market?.question ?? `Market #${prediction.market_id}`}</h3>
          </div>
          <Badge variant={prediction.recommended_action === "skip" ? "outline" : "default"}>
            {prediction.recommended_action.replace("_", " ").toUpperCase()}
          </Badge>
        </CardHeader>
        <CardContent className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div><div className="text-xs text-muted-foreground">AI</div><div>{formatPercent(aiProb)}</div></div>
          <div><div className="text-xs text-muted-foreground">Market</div><div>{formatPercent(mktProb)}</div></div>
          <div><div className="text-xs text-muted-foreground">Edge</div><div className={edgeColor}>{(edge * 100).toFixed(1)}%</div></div>
          <div><div className="text-xs text-muted-foreground">Confidence</div><div>{formatPercent(Number(prediction.confidence))}</div></div>
        </CardContent>
      </Link>
    </Card>
  );
}
```

- [ ] **Step 2: `PredictionList.tsx`**

```tsx
"use client";
import * as React from "react";
import { usePredictionHistory } from "@/hooks/usePredictions";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PredictionCard } from "./PredictionCard";

type Filter = "all" | "trade" | "skip";

export function PredictionList() {
  const { data, isLoading } = usePredictionHistory();
  const [filter, setFilter] = React.useState<Filter>("all");

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  const items = (data ?? []).filter((p) => {
    if (filter === "trade") return p.recommended_action !== "skip";
    if (filter === "skip") return p.recommended_action === "skip";
    return true;
  });
  return (
    <div className="space-y-4">
      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="trade">Trades</TabsTrigger>
          <TabsTrigger value="skip">Skipped</TabsTrigger>
        </TabsList>
      </Tabs>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No predictions yet.</p>
      ) : (
        <div className="space-y-3">{items.map((p) => <PredictionCard key={p.id} prediction={p} />)}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: `frontend/src/app/predictions/page.tsx`**

```tsx
import { PredictionList } from "@/components/predictions/PredictionList";

export default function PredictionsPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Predictions</h1>
        <p className="text-muted-foreground">Every AI prediction the system has made — including skipped ones (audit trail).</p>
      </header>
      <PredictionList />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/predictions/page.tsx frontend/src/components/predictions/
git commit -m "feat(frontend): /predictions list with filter tabs"
```

---

### Task 5.4: Prediction detail `/predictions/[id]`

**Files:**
- Create: `frontend/src/app/predictions/[id]/page.tsx`
- Create: `frontend/src/components/predictions/PredictionDetail.tsx`

- [ ] **Step 1: `PredictionDetail.tsx`**

```tsx
"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { usePredictionDetail } from "@/hooks/usePredictions";
import { formatPercent } from "@/lib/format";

export function PredictionDetail({ id }: { id: number }) {
  const { data, isLoading } = usePredictionDetail(id);
  if (isLoading) return <Skeleton className="h-[600px] w-full" />;
  if (!data) return <p className="text-muted-foreground">Prediction not found.</p>;

  const aiProb = Number(data.predicted_probability);
  const mktProb = Number(data.market_probability);
  const edge = Number(data.edge);
  const conf = Number(data.confidence);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Prediction #{data.id}</h1>
          <p className="text-muted-foreground font-mono text-sm">{data.created_at}</p>
        </div>
        <Badge variant={data.recommended_action === "skip" ? "outline" : "default"} className="text-base">
          {data.recommended_action.replace("_", " ").toUpperCase()}
        </Badge>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="AI predicted" value={formatPercent(aiProb)} />
        <Stat label="Polymarket" value={formatPercent(mktProb)} />
        <Stat label="Edge" value={`${(edge * 100).toFixed(1)}%`} cls={edge > 0 ? "text-success" : edge < 0 ? "text-destructive" : ""} />
        <Stat label="Confidence" value={formatPercent(conf)} />
      </div>
      <Card>
        <CardHeader><CardTitle>Reasoning</CardTitle></CardHeader>
        <CardContent className="prose prose-sm dark:prose-invert max-w-none">{data.reasoning}</CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <FactorList title="Key factors" items={data.key_factors} tone="success" />
        <FactorList title="Risk factors" items={data.risk_factors} tone="destructive" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Technical">{data.technical_analysis}</Section>
        <Section title="Sentiment">{data.sentiment_analysis}</Section>
        <Section title="News">{data.news_impact}</Section>
        <Section title="On-chain">{data.onchain_analysis}</Section>
      </div>
      <Card>
        <CardHeader><CardTitle>Data snapshot</CardTitle></CardHeader>
        <CardContent>
          <pre className="text-xs overflow-x-auto bg-muted p-4 rounded">{JSON.stringify(data.data_snapshot, null, 2)}</pre>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">{label}</CardTitle></CardHeader>
      <CardContent><div className={`text-2xl font-bold ${cls ?? ""}`}>{value}</div></CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">{title}</CardTitle></CardHeader>
      <CardContent className="text-sm text-muted-foreground">{children}</CardContent>
    </Card>
  );
}

function FactorList({ title, items, tone }: { title: string; items: string[]; tone: "success" | "destructive" }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">{title}</CardTitle></CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2">
              <span className={tone === "success" ? "text-success" : "text-destructive"}>•</span>
              <span>{it}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: `frontend/src/app/predictions/[id]/page.tsx`**

```tsx
import { PredictionDetail } from "@/components/predictions/PredictionDetail";

export default function PredictionDetailPage({ params }: { params: { id: string } }) {
  const id = parseInt(params.id, 10);
  return (
    <div className="container py-8">
      {Number.isNaN(id) ? <p className="text-destructive">Invalid prediction id.</p> : <PredictionDetail id={id} />}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/predictions/[id] frontend/src/components/predictions/PredictionDetail.tsx
git commit -m "feat(frontend): /predictions/[id] detail page"
```

---

### Task 5.5: Leaderboard `/leaderboard`

**Files:**
- Create: `frontend/src/app/leaderboard/page.tsx`
- Create: `frontend/src/components/leaderboard/LeaderboardTable.tsx`

- [ ] **Step 1: `LeaderboardTable.tsx`**

```tsx
"use client";
import { useLeaderboard } from "@/hooks/useStats";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Trophy, Medal } from "lucide-react";
import { shortAddress } from "@/lib/format";

const RANK_ICON = (rank: number) =>
  rank === 1 ? <Trophy className="h-4 w-4 text-yellow-500" /> :
  rank === 2 ? <Medal className="h-4 w-4 text-zinc-400" /> :
  rank === 3 ? <Medal className="h-4 w-4 text-amber-700" /> :
  <span className="text-muted-foreground">#{rank}</span>;

export function LeaderboardTable() {
  const { data, isLoading } = useLeaderboard();
  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No depositors indexed yet. The leaderboard requires on-chain deposit-event indexing —
        run the backend seed script after some deposits are made on-chain.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">Rank</TableHead>
          <TableHead>Wallet</TableHead>
          <TableHead className="text-right">Deposited</TableHead>
          <TableHead className="text-right">Current value</TableHead>
          <TableHead className="text-right">Profit</TableHead>
          <TableHead className="text-right">Profit %</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((row) => {
          const profit = Number(row.profit);
          return (
            <TableRow key={row.wallet}>
              <TableCell>{RANK_ICON(row.rank)}</TableCell>
              <TableCell className="font-mono">{shortAddress(row.wallet)}</TableCell>
              <TableCell className="text-right font-mono">${row.deposited}</TableCell>
              <TableCell className="text-right font-mono">${row.current_value}</TableCell>
              <TableCell className={`text-right font-mono ${profit > 0 ? "text-success" : profit < 0 ? "text-destructive" : ""}`}>
                {profit >= 0 ? "+" : ""}${row.profit}
              </TableCell>
              <TableCell className="text-right font-mono">{row.profit_pct}%</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: `frontend/src/app/leaderboard/page.tsx`**

```tsx
import { LeaderboardTable } from "@/components/leaderboard/LeaderboardTable";

export default function LeaderboardPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Leaderboard</h1>
        <p className="text-muted-foreground">Top depositors ranked by profit.</p>
      </header>
      <LeaderboardTable />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/leaderboard frontend/src/components/leaderboard/
git commit -m "feat(frontend): /leaderboard table"
```

---

### Task 5.6: Admin `/admin`

**Files:**
- Create: `frontend/src/app/admin/page.tsx`
- Create: `frontend/src/components/admin/SystemStatus.tsx`
- Create: `frontend/src/components/admin/AdminActions.tsx`

- [ ] **Step 1: `SystemStatus.tsx`**

```tsx
"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSystemStatus } from "@/hooks/useSystem";

export function SystemStatus() {
  const { data, isLoading } = useSystemStatus();
  return (
    <Card>
      <CardHeader><CardTitle>System status</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Row label="Paused" value={data?.paused} ok={!data?.paused} loading={isLoading} />
        <Row label="Scheduler" value={data?.scheduler_running} ok={!!data?.scheduler_running} loading={isLoading} />
        <Row label="Monitor" value={data?.monitor_running} ok={!!data?.monitor_running} loading={isLoading} />
      </CardContent>
    </Card>
  );
}

function Row({ label, value, ok, loading }: { label: string; value: boolean | undefined; ok: boolean; loading: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      {loading ? <Badge variant="outline">…</Badge> :
        <Badge variant={ok ? "default" : "destructive"}>{value ? "true" : "false"}</Badge>}
    </div>
  );
}
```

- [ ] **Step 2: `AdminActions.tsx`**

```tsx
"use client";
import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAdminStore } from "@/store/admin";
import { useScanMarket } from "@/hooks/useMarkets";
import { useTriggerPrediction } from "@/hooks/usePredictions";
import { useGenerateStrategy } from "@/hooks/useStrategies";
import { useExecuteTrade } from "@/hooks/useTrades";
import { usePauseSystem, useResumeSystem } from "@/hooks/useSystem";

export function AdminActions() {
  const token = useAdminStore((s) => s.token);
  const setToken = useAdminStore((s) => s.setToken);
  const scan = useScanMarket();
  const predict = useTriggerPrediction();
  const generate = useGenerateStrategy();
  const execute = useExecuteTrade();
  const pause = usePauseSystem();
  const resume = useResumeSystem();

  const wrap = (label: string, m: { mutateAsync: () => Promise<unknown> }) => async () => {
    try { await m.mutateAsync(); toast.success(`${label} OK`); }
    catch (e) { toast.error(`${label} failed`, { description: (e as Error).message }); }
  };

  return (
    <Card>
      <CardHeader><CardTitle>Admin actions</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="admin-token">Admin API key</Label>
          <Input id="admin-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} />
          <p className="text-xs text-muted-foreground">Stored in localStorage; matches backend ADMIN_API_KEY.</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" onClick={wrap("Market scan", scan)} disabled={scan.isPending}>1. Scan market</Button>
          <Button variant="outline" onClick={wrap("Prediction", predict)} disabled={predict.isPending}>2. Predict</Button>
          <Button variant="outline" onClick={wrap("Generate", generate)} disabled={generate.isPending}>3. Generate strategy</Button>
          <Button variant="outline" onClick={wrap("Execute", execute)} disabled={execute.isPending}>4. Execute trade</Button>
          <Button variant="destructive" onClick={wrap("Pause", pause)} disabled={pause.isPending}>Pause</Button>
          <Button variant="default" onClick={wrap("Resume", resume)} disabled={resume.isPending}>Resume</Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: `frontend/src/app/admin/page.tsx`**

```tsx
import { SystemStatus } from "@/components/admin/SystemStatus";
import { AdminActions } from "@/components/admin/AdminActions";

export default function AdminPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Admin</h1>
        <p className="text-muted-foreground">Trigger pipeline steps manually and pause/resume the system.</p>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        <SystemStatus />
        <AdminActions />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/admin frontend/src/components/admin/
git commit -m "feat(frontend): /admin page (status + manual pipeline + pause/resume)"
```

---

## Phase 6 — Integration & Demo Seed

### Task 6.1: Backend seed script (calls admin endpoints)

**Files:**
- Create: `backend/scripts/seed_demo.py`

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""Idempotent demo data seeding via admin REST endpoints.

Run this AFTER the backend is up so the dashboard is not empty:

    cd backend && uv run python scripts/seed_demo.py

Order: market scan → prediction → strategy → trade execute. If any step
fails (e.g. OpenAI key missing), it prints a diagnostic and continues —
the goal is "best-effort visible data," not strict success.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx

BASE = os.environ.get("API_BASE", "http://localhost:8000/api/v1")
TOKEN = os.environ.get("ADMIN_API_KEY", "dev_admin_key")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def call(method: str, path: str) -> tuple[int, Any]:
    with httpx.Client(timeout=60.0) as client:
        resp = client.request(method, f"{BASE}{path}", headers=HEADERS)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, resp.text


def step(name: str, method: str, path: str) -> bool:
    print(f"→ {name} ({method} {path})")
    code, body = call(method, path)
    ok = 200 <= code < 300
    print(f"  {code} {body if not ok else 'OK'}")
    return ok


def main() -> int:
    health = httpx.get(f"{BASE.replace('/api/v1', '')}/health", timeout=5)
    if health.status_code != 200:
        print(f"Backend not up at {BASE} — start it first.", file=sys.stderr)
        return 1

    step("Resume system (in case paused)", "POST", "/system/resume")
    step("Scan today's market", "POST", "/markets/scan")
    time.sleep(1)
    step("Trigger AI prediction", "POST", "/predictions/trigger")
    time.sleep(1)
    step("Generate strategy", "POST", "/strategies/generate")
    time.sleep(1)
    step("Execute trade", "POST", "/trades/execute")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Mark executable + commit**

Run: `chmod +x backend/scripts/seed_demo.py`

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat(backend): scripts/seed_demo.py — idempotent admin-driven demo seed"
```

---

### Task 6.2: Root orchestration scripts

**Files:**
- Create: `package.json` (repo root)
- Create: `scripts/dev.sh`
- Create: `scripts/seed-demo.sh`

- [ ] **Step 1: Create root `package.json` (just for `concurrently`)**

```json
{
  "name": "polymarket-ai-monorepo",
  "version": "1.0.0",
  "private": true,
  "description": "Orchestration scripts for the full PolyPredict stack",
  "scripts": {
    "dev:chain": "cd contracts && npm run node",
    "dev:deploy": "cd contracts && npm run deploy:local-full",
    "dev:abi": "cd contracts && npm run export:abi && cp exports/abi/*.json ../frontend/src/lib/abi/",
    "dev:backend": "cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
    "dev:frontend": "cd frontend && pnpm dev",
    "dev:all": "concurrently -n chain,backend,frontend -c blue,green,magenta \"npm:dev:chain\" \"npm:dev:backend\" \"npm:dev:frontend\"",
    "seed": "bash scripts/seed-demo.sh"
  },
  "devDependencies": {
    "concurrently": "^9.0.1"
  }
}
```

- [ ] **Step 2: Create `scripts/dev.sh`**

```bash
#!/usr/bin/env bash
# Boots the full PolyPredict stack for local demo:
#   1. Hardhat node on :8545
#   2. Deploy contracts + write addresses
#   3. Export ABIs to frontend
#   4. Sync addresses into backend/.env and frontend/.env.local
#   5. Start backend (:8000) + frontend (:3000)
#
# Usage:  ./scripts/dev.sh
# Stop:   Ctrl-C cleans up everything
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN="\033[32m"; YELLOW="\033[33m"; RESET="\033[0m"
log() { printf "${GREEN}[dev]${RESET} %s\n" "$1"; }
warn() { printf "${YELLOW}[dev]${RESET} %s\n" "$1"; }

cleanup() {
  log "stopping background processes…"
  jobs -p | xargs -r kill 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "1/5 starting Hardhat node…"
(cd contracts && npm run node) > /tmp/hardhat.log 2>&1 &
HARDHAT_PID=$!
sleep 3

log "2/5 deploying contracts…"
(cd contracts && npm run deploy:local-full) | tee /tmp/deploy.log

VAULT=$(grep "PolyVault proxy:" /tmp/deploy.log | awk '{print $NF}')
USDC=$(grep "MockUSDC:" /tmp/deploy.log | awk '{print $NF}')
log "  Vault=$VAULT  USDC=$USDC"

log "3/5 exporting ABIs to frontend…"
(cd contracts && npm run export:abi)
mkdir -p frontend/src/lib/abi
cp contracts/exports/abi/PolyVault.json contracts/exports/abi/MockUSDC.json frontend/src/lib/abi/

log "4/5 wiring .env files…"
# Backend
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi
sed -i.bak "s|^VAULT_CONTRACT_ADDRESS=.*|VAULT_CONTRACT_ADDRESS=$VAULT|" backend/.env
sed -i.bak "s|^USDC_CONTRACT_ADDRESS=.*|USDC_CONTRACT_ADDRESS=$USDC|"  backend/.env
rm -f backend/.env.bak
# Frontend
if [ ! -f frontend/.env.local ]; then cp frontend/.env.local.example frontend/.env.local; fi
sed -i.bak "s|^NEXT_PUBLIC_VAULT_ADDRESS=.*|NEXT_PUBLIC_VAULT_ADDRESS=$VAULT|" frontend/.env.local
sed -i.bak "s|^NEXT_PUBLIC_USDC_ADDRESS=.*|NEXT_PUBLIC_USDC_ADDRESS=$USDC|"   frontend/.env.local
rm -f frontend/.env.local.bak

log "5/5 starting backend + frontend (Ctrl-C to stop everything)…"
(cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
(cd frontend && pnpm dev) &
wait
```

- [ ] **Step 3: Create `scripts/seed-demo.sh`**

```bash
#!/usr/bin/env bash
# Seeds the backend with one round of fake market+prediction+strategy+trade
# data so the dashboard is populated. Backend must already be running.
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv run python scripts/seed_demo.py
```

- [ ] **Step 4: Mark executable**

Run: `chmod +x scripts/dev.sh scripts/seed-demo.sh`

- [ ] **Step 5: Commit**

```bash
git add package.json scripts/
git commit -m "feat(scripts): one-command dev orchestration (chain+backend+frontend) + demo seed"
```

---

### Task 6.3: Update `.env.example` at repo root + .gitignore

**Files:**
- Create: `.env.example` (root)
- Modify: `.gitignore` (root)

- [ ] **Step 1: Create root `.env.example`**

```env
# Repo-root env (currently unused — backend & frontend each have their own .env).
# Kept for documentation: the values below are the demo defaults and match
# scripts/dev.sh expectations.
#
# See backend/.env.example and frontend/.env.local.example for the real envs.
```

- [ ] **Step 2: Update root `.gitignore`**

```
# Editor
.idea/
.vscode/

# OS
.DS_Store

# Node
node_modules/

# Python  
**/__pycache__/
*.pyc
*.pyo
.venv/
.pytest_cache/
backend/polypredict.db

# Local env
**/.env
**/.env.local
!**/.env.example
!**/.env.local.example

# Build artifacts
**/.next/
**/dist/
**/coverage/
playwright-report/
test-results/
```

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore(repo): root .env.example + .gitignore for demo flow"
```

---

## Phase 7 — Smoke Tests + README

### Task 7.1: Playwright dashboard smoke

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/src/tests/e2e/dashboard.spec.ts`

- [ ] **Step 1: Create `frontend/playwright.config.ts`**

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./src/tests/e2e",
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
```

- [ ] **Step 2: Create `frontend/src/tests/e2e/dashboard.spec.ts`**

```typescript
import { test, expect } from "@playwright/test";

test("dashboard renders with header + KPI cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: /PolyPredict AI/ })).toBeVisible();
  // KPI cards are present even when API returns empty data
  await expect(page.getByText("TVL")).toBeVisible();
  await expect(page.getByText("Win rate")).toBeVisible();
  await expect(page.getByText("Total PnL")).toBeVisible();
  await expect(page.getByText("Share price")).toBeVisible();
});

test("vault page shows connect-wallet prompt when not connected", async ({ page }) => {
  await page.goto("/vault");
  await expect(page.getByRole("heading", { name: "Vault" })).toBeVisible();
  await expect(page.getByText(/Connect a wallet/i)).toBeVisible();
});

test("predictions page renders the empty state", async ({ page }) => {
  await page.goto("/predictions");
  await expect(page.getByRole("heading", { name: "Predictions" })).toBeVisible();
});

test("admin page renders status + actions", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();
  await expect(page.getByText("System status")).toBeVisible();
  await expect(page.getByText("Admin actions")).toBeVisible();
});
```

- [ ] **Step 3: Install Playwright browser, run tests against backend-less app**

Run:
```bash
cd frontend && pnpm e2e:install && pnpm e2e
```
Expected: 4 tests PASS (the page renders even when the backend is unreachable; queries enter error state but skeletons / empty states show).

- [ ] **Step 4: Commit**

```bash
git add frontend/playwright.config.ts frontend/src/tests/e2e/
git commit -m "test(frontend): Playwright smoke tests — dashboard/vault/predictions/admin"
```

---

### Task 7.2: README with full local demo walkthrough

**Files:**
- Modify: `README.md` (root)

- [ ] **Step 1: Append a "Quick local demo" section near the top**

Locate the "## 快速开始" section in the existing `README.md` and replace its body (the part that currently says only `contracts/` is runnable) with the following — keep the surrounding heading structure intact:

```markdown
## 快速开始

完整三层栈本地一键启动。

### 前置依赖

| 工具 | 版本 |
|---|---|
| Node.js | ≥ 20 |
| pnpm | ≥ 9 (`npm i -g pnpm@9`) |
| Python | 3.12 |
| uv | latest (`pip install uv`) |
| MetaMask | 浏览器插件 |

### 一键启动（推荐）

```bash
# 1. 安装依赖
cd contracts && npm install && cd ..
cd backend && uv sync && cd ..
cd frontend && pnpm install && cd ..

# 2. 启动全栈（Hardhat 链 + 后端 + 前端）
./scripts/dev.sh

# 3. 在另一个终端：种子数据（让仪表板有可视内容）
./scripts/seed-demo.sh
```

启动后：
- Hardhat 链：`http://localhost:8545`（chainId 31337）
- 后端：`http://localhost:8000`（OpenAPI: `/docs`）
- 前端：`http://localhost:3000`

`scripts/dev.sh` 自动完成：
1. 启动 Hardhat node
2. 部署 `MockUSDC` + `PolyVault`(UUPS proxy)，给前 5 个测试账户各 mint 1,000,000 USDC
3. 把 ABI 拷贝到 `frontend/src/lib/abi/`
4. 把合约地址写入 `backend/.env` 和 `frontend/.env.local`
5. 启动 backend + frontend

### MetaMask 配置

1. 添加自定义网络：
   - Name: `Hardhat Localhost`
   - RPC URL: `http://127.0.0.1:8545`
   - Chain ID: `31337`
   - Symbol: `ETH`
2. 导入 Hardhat 默认账号（私钥见 hardhat node 启动日志），账户 #0 既是金库管理员，#1-4 各持有 1,000,000 测试 USDC，可用于演示存款。

### 三个独立终端启动（替代方案）

如果想分别看日志：

```bash
# Terminal 1
cd contracts && npm run node

# Terminal 2 (等 #1 起来后)
cd contracts && npm run deploy:local-full
cd contracts && npm run export:abi
cp contracts/exports/abi/*.json frontend/src/lib/abi/

# Terminal 3
cd backend && uv run uvicorn app.main:app --reload

# Terminal 4
cd frontend && pnpm dev
```

### 演示流程

1. 浏览器打开 `http://localhost:3000`
2. 顶部点 **Connect Wallet** → MetaMask → 选 Hardhat Localhost
3. 进 `/vault` → 输入 100 → **Approve USDC** → **Deposit**
4. 进 `/admin` → 顺序点 *Scan market* → *Predict* → *Generate strategy* → *Execute trade*
5. 回 `/`（Dashboard）查看 TVL、AI 预测、近期交易
6. 进 `/vault` → 申请取款 → 等 24h（或直接管理员加速：用 `cast rpc evm_increaseTime 86400 && cast rpc evm_mine` 跨过延迟期）→ **Execute**

### 必填 API Keys

只有这两个 key 是必需的，其余服务已自动降级：

```env
# backend/.env
OPENAI_API_KEY=sk-...
POLYMARKET_API_KEY=...
POLYMARKET_API_SECRET=...
POLYMARKET_PASSPHRASE=...
```

未配 `CRYPTOPANIC_API_KEY` 时新闻列表为空（PRD §3.2.4 — news 是可选输入）。Binance 和 Fear&Greed 是公开 API，无需 key。
```

- [ ] **Step 2: Update the "## 开发路线" table to mark frontend done**

Replace the existing table rows in "## 开发路线" with:

```markdown
| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | ✅ 已完成 | PolyVault 合约 + 单元测试 |
| Phase 2 | ✅ 已完成 | 后端 FastAPI 服务（M0-M8 全部完成）|
| Phase 3 | ✅ 已完成 | 前端 Next.js 14 仪表板 + 本地一键演示 |
| Phase 4 | ⏳ 待启动 | Polygon Amoy 测试网部署与端到端验证 |
| Phase 5 | ⏳ 待启动 | Polygon 主网部署 + 公开 Beta |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): full local-demo walkthrough + updated roadmap"
```

---

### Task 7.3: Final smoke — full stack boots end-to-end

- [ ] **Step 1: Boot via `dev.sh`**

In a fresh terminal:
```bash
./scripts/dev.sh
```
Wait until you see logs from all three layers. In ANOTHER terminal:

```bash
curl -s http://localhost:8000/health                 # → {"status":"ok"}
curl -s http://localhost:8000/api/v1/stats/overview  # → 200 with valid JSON
curl -s http://localhost:3000 | grep -i "PolyPredict"  # → matches
```

Expected: all three checks succeed.

- [ ] **Step 2: Stop and document any deviations**

Ctrl-C the dev script. If anything failed (port conflict, missing dep, etc.), record in a follow-up `docs/superpowers/specs/2026-05-10-issues-found.md`.

- [ ] **Step 3: Run full test suite once more**

```bash
cd contracts && npm test
cd ../backend && uv run pytest
cd ../frontend && pnpm test && pnpm typecheck
```
Expected: all green.

- [ ] **Step 4: Final commit if anything was tweaked**

```bash
git add -A
git commit -m "chore: final smoke fixes" --allow-empty
```

---

## Self-Review Checklist (run before handoff)

- [ ] **Spec coverage:** every PRD-frontend page (`/`, `/vault`, `/predictions`, `/predictions/[id]`, `/leaderboard`, `/admin`) has a Phase 5 task. ✓
- [ ] **All vault contract methods used by the frontend are wired:** `deposit`, `requestWithdraw`, `cancelWithdraw`, `executeWithdraw`, `convertToAssets`, `balanceOf`, `getWithdrawalRequest`, `withdrawalDelay`, `totalAssets`, `strategyDebt`, `totalSupply` (Tasks 4.1, 4.3). ✓
- [ ] **All 20+ backend endpoints have a hook:** markets/today, markets/scan, predictions/today, predictions/history, predictions/{id}, predictions/trigger, strategies/active, strategies/history, strategies/generate, trades/active, trades/history, trades/execute, stats/overview, stats/daily, stats/vault, stats/leaderboard, system/status, system/pause, system/resume (Tasks 4.4, 4.6, 4.7). ✓
- [ ] **API keys handled:** CryptoPanic graceful (Task 0.1), news degradation (Task 0.2), .env.example marks required vs optional (Task 0.4). ✓
- [ ] **CORS:** Task 0.3 — verified with two integration tests. ✓
- [ ] **Hardhat localhost:** auto-deploy script (Task 1.1) + ABI export (Task 1.2). ✓
- [ ] **Demo orchestration:** `scripts/dev.sh` writes addresses into both backend and frontend env files (Task 6.2). ✓
- [ ] **No placeholders in steps.** Every "Step N" includes either complete code, an exact command, or a documented file copy/edit. ✓
- [ ] **TDD applied** for backend behavioral changes (Tasks 0.1, 0.2, 0.3) and pure frontend libs (Task 2.5: format + api). UI components use Playwright smoke (Task 7.1) — appropriate for visual code per PRD's testing strategy in spec §7. ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-10-frontend-and-integration.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Phase 5 tasks (5.1–5.6) parallelize well across 6 subagents once Phase 4 completes.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints for review.

**Which approach?**
