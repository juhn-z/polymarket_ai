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
