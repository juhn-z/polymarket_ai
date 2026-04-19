# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This is a multi-component project for an AI-driven Polymarket prediction vault. Only the smart contract is currently implemented; backend and frontend exist as Chinese-language PRDs only.

- `contracts/` — Hardhat + TypeScript Solidity project (the only code-bearing directory).
- `docs/PRD-smart-contract.md` — spec the contract implements.
- `docs/PRD-backend.md` — planned Python/FastAPI service (not yet built).
- `docs/PRD-frontend.md` — planned Next.js dashboard (not yet built).

When asked to "implement the backend" or "build the frontend," start from the corresponding PRD in `docs/`.

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
