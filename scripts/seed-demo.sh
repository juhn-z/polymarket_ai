#!/usr/bin/env bash
# Seeds the backend with one round of fake market+prediction+strategy+trade
# data so the dashboard is populated. Backend must already be running.
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv run python scripts/seed_demo.py
