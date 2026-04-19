"""Unit tests for FearGreedHttpClient (alternative.me)."""
from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from app.adapters.fear_greed import FearGreedHttpClient


@pytest.fixture
def client() -> FearGreedHttpClient:
    return FearGreedHttpClient(base_url="https://api.alternative.me/fng/")


@respx.mock
async def test_get_index_parses_alternative_me_response(client: FearGreedHttpClient) -> None:
    # Alternative.me returns {"data": [{"value": "42", "value_classification": "Fear",
    #   "timestamp": "1712361600", ...}, ...]}
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "Fear and Greed Index",
                "data": [
                    {"value": "42", "value_classification": "Fear", "timestamp": "1712361600"},
                    {"value": "55", "value_classification": "Greed", "timestamp": "1712275200"},
                ],
                "metadata": {"error": None},
            },
        )
    )

    points = await client.get_index(days=2)

    assert len(points) == 2
    assert points[0].value == 42
    assert points[0].label == "Fear"
    assert points[0].at == date(2024, 4, 6)
    assert points[1].value == 55
    assert points[1].label == "Greed"


@respx.mock
async def test_get_index_sends_limit_param(client: FearGreedHttpClient) -> None:
    route = respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    await client.get_index(days=7)
    assert route.called
    assert route.calls.last.request.url.params["limit"] == "7"
