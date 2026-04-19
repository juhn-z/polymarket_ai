"""Live smoke test against alternative.me Fear & Greed API."""
from __future__ import annotations

import pytest

from app.adapters.fear_greed import FearGreedHttpClient

pytestmark = pytest.mark.live


async def test_get_index_returns_valid_points() -> None:
    client = FearGreedHttpClient()
    try:
        points = await client.get_index(days=3)
    finally:
        await client.aclose()

    assert len(points) >= 1
    for p in points:
        assert 0 <= p.value <= 100
        assert p.label
