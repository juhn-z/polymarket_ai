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
