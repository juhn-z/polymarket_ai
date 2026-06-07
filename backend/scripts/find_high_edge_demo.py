#!/usr/bin/env python3
"""Find a Polymarket BTC market where AI is likely to find naturally high edge.

Heuristic — rank candidates by |expected_yes - market_yes_price|, where
expected_yes is a crude function of BTC current spot vs the market's
threshold. AI gives the actual probability later; we just pre-filter
to candidates worth AI's time.

The scanner's `idempotent one market per scan_date` rule blocks re-runs.
This script bypasses by clearing today's market+prediction+strategy
rows first, then writing the chosen high-edge market directly. Then it
triggers /predictions/trigger and /strategies/generate via the running
backend's admin HTTP API.

Usage (backend must be running on :8000):
    cd backend && uv run python scripts/find_high_edge_demo.py
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx

from app.adapters.binance import BinanceHttpClient
from app.adapters.polymarket_gamma import PolymarketGammaHttpClient
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.domain.markets import Market
from app.models import Base  # noqa: F401 (ensure ORM registered)
from app.repositories.market_repository_sa import SqlAlchemyMarketRepository

API = os.environ.get("API_BASE", "http://localhost:8000/api/v1")
TOKEN = os.environ.get("ADMIN_API_KEY", "dev_admin_key")
TOP_N = 5


def _clear_today(db_path: str) -> None:
    """Delete today's market + cascade so scanner-idempotency doesn't fire."""
    conn = sqlite3.connect(db_path)
    try:
        # Strategies → predictions → markets (FK order doesn't matter in sqlite
        # without FK enforcement, but keep the order anyway for clarity).
        conn.execute("DELETE FROM strategies")
        conn.execute("DELETE FROM predictions")
        conn.execute("DELETE FROM markets")
        conn.commit()
        print("cleared existing markets/predictions/strategies")
    finally:
        conn.close()


def _expected_yes(btc_price: Decimal, threshold: int, hours_to_resolution: float) -> Decimal:
    """Cheap heuristic for AI's likely calibrated probability.

    BTC well above threshold near resolution → near certain YES.
    BTC well below threshold near resolution → near certain NO.
    Closer to threshold → closer to 50%.
    """
    distance_pct = (btc_price - Decimal(threshold)) / Decimal(threshold)
    # Volatility budget: ~2% per day is a reasonable rough ATR for BTC.
    daily_vol = Decimal("0.02")
    days = Decimal(str(max(hours_to_resolution / 24.0, 0.5)))
    sigma = daily_vol * days.sqrt() if hasattr(days, "sqrt") else daily_vol * Decimal(str(float(days) ** 0.5))
    # crude z-score
    z = distance_pct / sigma if sigma > 0 else Decimal("0")
    # squash to (0, 1) — sigmoid-ish without scipy
    # P(yes) ≈ 0.5 + 0.5 * tanh(z), bounded to [0.02, 0.98]
    # tanh via (e^x - e^-x)/(e^x + e^-x); for our range use a simple piecewise approx
    z_f = float(z)
    import math

    p = 0.5 + 0.5 * math.tanh(z_f)
    return Decimal(str(max(0.02, min(0.98, p))))


async def main() -> int:
    settings = get_settings()

    gamma = PolymarketGammaHttpClient(base_url=settings.polymarket_gamma_api_url)
    binance = BinanceHttpClient(base_url=settings.binance_api_url)

    try:
        # 1. BTC current spot
        ticker = await binance.get_24h_ticker("BTCUSDT")
        btc_price = ticker.last_price
        print(f"BTC spot: ${btc_price:.2f}")

        # 2. All active "Bitcoin above" events
        events = await gamma.search_events(tag="bitcoin")
        print(f"gamma returned {len(events)} events")

        now = datetime.now(timezone.utc)
        candidates: list[tuple[Decimal, Decimal, "GammaMarket", "GammaEvent", float]] = []  # type: ignore[name-defined]
        for event in events:
            if not event.active:
                continue
            if "bitcoin above" not in event.title.lower():
                continue
            markets = await gamma.get_event_markets(event.id)
            for m in markets:
                # Need a reasonable resolution window (1h..14d)
                if m.target_date is None:
                    continue
                target_dt = datetime.combine(m.target_date, datetime.min.time(), tzinfo=timezone.utc)
                hours = (target_dt - now).total_seconds() / 3600
                if hours < 1 or hours > 14 * 24:
                    continue
                # Skip pinned markets — no room for edge there
                if m.yes_price < Decimal("0.05") or m.yes_price > Decimal("0.95"):
                    continue
                if m.volume_24h < Decimal("1000"):
                    continue

                expected = _expected_yes(btc_price, m.price_threshold, hours)
                heuristic_edge = abs(expected - m.yes_price)
                candidates.append((heuristic_edge, expected, m, event, hours))

        candidates.sort(key=lambda c: -c[0])
        if not candidates:
            print("no eligible candidates after filtering")
            return 1

        print(f"\nTop {TOP_N} candidates by heuristic edge:")
        for edge, expected, m, event, hours in candidates[:TOP_N]:
            print(
                f"  heuristic={edge:.2f} "
                f"(expected_yes~{expected:.2f} vs market={m.yes_price:.2f}) "
                f"| threshold=${m.price_threshold:,} target={m.target_date} "
                f"hrs={hours:.0f} vol24h=${m.volume_24h:,.0f}"
            )

    finally:
        await gamma.aclose()
        await binance.aclose()

    # 3. AI-evaluate Top N candidates, pick the largest |edge|
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "").lstrip("./")
    if db_path.startswith("/"):
        full = Path(db_path)
    else:
        full = Path(__file__).parent.parent / db_path

    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    headers = {"Authorization": f"Bearer {TOKEN}"}

    results: list[tuple[float, dict, "GammaMarket", "GammaEvent"]] = []  # type: ignore[name-defined]
    with httpx.Client(timeout=120.0) as c:
        for i, (heuristic, _, m, event, _) in enumerate(candidates[:TOP_N]):
            print(f"\n--- candidate {i+1}/{TOP_N}: {event.slug} ${m.price_threshold:,} (yes={m.yes_price:.2%}, heuristic={heuristic:.2f}) ---")
            # Reset DB so the predictor sees this candidate as today's market
            if full.exists():
                _clear_today(str(full))
            async with session_factory() as session:
                repo = SqlAlchemyMarketRepository(session)
                market = Market.from_gamma(
                    m,
                    event_slug=event.slug,
                    scan_date=now.date(),
                    selected_at=now,
                )
                await repo.save(market)
                await session.commit()
            r = c.post(f"{API}/predictions/trigger", headers=headers)
            if r.status_code != 200:
                print(f"  predict failed: {r.status_code} {r.text[:200]}")
                continue
            pred = r.json()
            edge = abs(float(pred["edge"]))
            print(f"  AI={pred['predicted_probability']} mkt={pred['market_probability']} "
                  f"edge={pred['edge']} conf={pred['confidence']} action={pred['recommended_action']}")
            results.append((edge, pred, m, event))
            if edge >= 0.25:
                print(f"  ✓ HIT — edge {edge:.2%} >= 25%, stopping early")
                break

    await engine.dispose()

    if not results:
        print("\nAll candidates failed to produce a prediction")
        return 1

    # 4. Pick best edge, finalize DB to that candidate, run strategy
    results.sort(key=lambda r: -r[0])
    best_edge, best_pred, best_m, best_event = results[0]
    print(f"\n=== BEST: {best_event.slug} ${best_m.price_threshold:,} ===")
    print(f"  AI={best_pred['predicted_probability']} mkt={best_pred['market_probability']} "
          f"edge={best_pred['edge']} action={best_pred['recommended_action']}")

    # Make sure DB ends in the BEST candidate's state
    if full.exists():
        _clear_today(str(full))
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        repo = SqlAlchemyMarketRepository(session)
        market = Market.from_gamma(
            best_m, event_slug=best_event.slug, scan_date=now.date(), selected_at=now,
        )
        await repo.save(market)
        await session.commit()
    await engine.dispose()

    with httpx.Client(timeout=120.0) as c:
        r = c.post(f"{API}/predictions/trigger", headers=headers)
        if r.status_code != 200:
            print(f"final predict failed: {r.status_code} {r.text[:200]}")
            return 1
        r = c.post(f"{API}/strategies/generate", headers=headers)
        if r.status_code != 200:
            print(f"strategy failed: {r.status_code} {r.text[:200]}")
            return 1
        strat = r.json()
        print(f"\n--- final strategy ---")
        print(f"  action       ={strat['action']}")
        print(f"  side         ={strat['side']}")
        print(f"  position_size={strat['position_size']}")
        print(f"  entry_price  ={strat['entry_price']}")
        print(f"  take_profit  ={strat['take_profit']}")
        print(f"  stop_loss    ={strat['stop_loss']}")
        if strat["action"] == "skip":
            print(f"  skip_reason  ={strat['skip_reason']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
