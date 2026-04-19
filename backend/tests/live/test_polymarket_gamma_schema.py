"""Live smoke test against the real Polymarket Gamma API.

Run manually: ``pytest -m live tests/live/test_polymarket_gamma_schema.py``.
Skipped by default in CI / regular runs.
"""
from __future__ import annotations

import pytest

from app.adapters.polymarket_gamma import PolymarketGammaHttpClient

pytestmark = pytest.mark.live


async def test_search_events_returns_btc_events_with_expected_shape() -> None:
    client = PolymarketGammaHttpClient()
    try:
        events = await client.search_events(tag="bitcoin")
    finally:
        await client.aclose()

    assert isinstance(events, list)
    if events:
        e = events[0]
        assert e.id
        assert e.slug
        assert e.title
        assert e.active is True


async def test_get_event_markets_round_trips_for_first_btc_event() -> None:
    client = PolymarketGammaHttpClient()
    try:
        events = await client.search_events(tag="bitcoin")
        if not events:
            pytest.skip("No active bitcoin events on Polymarket right now")
        markets = await client.get_event_markets(events[0].id)
    finally:
        await client.aclose()

    # We don't assert non-empty (a brand-new event might have 0 parseable markets)
    # but if any markets came back, they should have all required fields populated.
    for m in markets:
        assert m.condition_id
        assert m.yes_token_id
        assert m.no_token_id
        assert m.price_threshold > 1000
        assert m.yes_price >= 0
        assert m.no_price >= 0
