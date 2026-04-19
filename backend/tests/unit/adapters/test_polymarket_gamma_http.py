"""Unit tests for PolymarketGammaHttpClient (real HTTP impl, mocked with respx)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from app.adapters.polymarket_gamma import PolymarketGammaHttpClient


@pytest.fixture
def client() -> PolymarketGammaHttpClient:
    return PolymarketGammaHttpClient(base_url="https://gamma-api.polymarket.com")


@respx.mock
async def test_search_events_filters_by_tag_and_active(client: PolymarketGammaHttpClient) -> None:
    route = respx.get("https://gamma-api.polymarket.com/events").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "10057",
                    "slug": "bitcoin-above-70000-on-friday",
                    "title": "Bitcoin above $70,000 on Friday?",
                    "active": True,
                    "closed": False,
                    "markets": [],
                },
                {
                    "id": "10058",
                    "slug": "bitcoin-above-65000-on-monday",
                    "title": "Bitcoin above $65,000 on Monday?",
                    "active": True,
                    "closed": True,  # should be excluded
                    "markets": [],
                },
            ],
        )
    )

    events = await client.search_events(tag="bitcoin")

    assert route.called
    assert route.calls.last.request.url.params["tag_slug"] == "bitcoin"
    assert route.calls.last.request.url.params["active"] == "true"
    assert route.calls.last.request.url.params["closed"] == "false"
    assert len(events) == 1
    assert events[0].id == "10057"
    assert events[0].slug == "bitcoin-above-70000-on-friday"
    assert events[0].title == "Bitcoin above $70,000 on Friday?"
    assert events[0].active is True


@respx.mock
async def test_get_event_markets_parses_outcome_prices_and_threshold(
    client: PolymarketGammaHttpClient,
) -> None:
    respx.get("https://gamma-api.polymarket.com/events/10057").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10057",
                "slug": "bitcoin-above-70000-on-friday",
                "title": "Bitcoin above $70,000 on Friday?",
                "active": True,
                "closed": False,
                "markets": [
                    {
                        "id": "500215",
                        "question": "Bitcoin above $70,000 on Friday?",
                        "conditionId": "0xbe6311035b2aace4f0c1acf2da5bc72c7f53342ec341d20c4b22b130f0b19a93",
                        "endDate": "2024-03-22T07:00:00Z",
                        "outcomes": '["Yes", "No"]',
                        "outcomePrices": '["0.42", "0.58"]',
                        "volume": "65416.039829",
                        "active": True,
                        "closed": False,
                        "clobTokenIds": '["yes-token-id-here", "no-token-id-here"]',
                    },
                ],
            },
        )
    )

    markets = await client.get_event_markets("10057")

    assert len(markets) == 1
    m = markets[0]
    assert m.condition_id == "0xbe6311035b2aace4f0c1acf2da5bc72c7f53342ec341d20c4b22b130f0b19a93"
    assert m.yes_token_id == "yes-token-id-here"
    assert m.no_token_id == "no-token-id-here"
    assert m.question == "Bitcoin above $70,000 on Friday?"
    assert m.price_threshold == 70000
    assert m.target_date == date(2024, 3, 22)
    assert m.yes_price == Decimal("0.42")
    assert m.no_price == Decimal("0.58")
    assert m.volume_24h == Decimal("65416.039829")


@respx.mock
async def test_get_event_markets_skips_malformed(client: PolymarketGammaHttpClient) -> None:
    """Markets without parseable threshold/prices/tokens are skipped, not raised."""
    respx.get("https://gamma-api.polymarket.com/events/10057").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10057",
                "slug": "bitcoin-above",
                "title": "x",
                "active": True,
                "closed": False,
                "markets": [
                    {
                        "id": "bad-1",
                        "question": "Will ETH flip?",  # no threshold
                        "conditionId": "0xbad",
                        "endDate": "2024-03-22T07:00:00Z",
                        "outcomes": '["Yes", "No"]',
                        "outcomePrices": '["0.42", "0.58"]',
                        "volume": "1",
                        "active": True,
                        "closed": False,
                        "clobTokenIds": '["a", "b"]',
                    },
                    {
                        "id": "good-1",
                        "question": "Bitcoin above $50,000?",
                        "conditionId": "0xgood",
                        "endDate": "2024-03-22T07:00:00Z",
                        "outcomes": '["Yes", "No"]',
                        "outcomePrices": '["0.42", "0.58"]',
                        "volume": "1",
                        "active": True,
                        "closed": False,
                        "clobTokenIds": '["a", "b"]',
                    },
                ],
            },
        )
    )

    markets = await client.get_event_markets("10057")

    assert len(markets) == 1
    assert markets[0].condition_id == "0xgood"
