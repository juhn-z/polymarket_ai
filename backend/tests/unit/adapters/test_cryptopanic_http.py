"""Unit tests for CryptoPanicHttpClient."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.cryptopanic import CryptoPanicHttpClient


@pytest.fixture
def client() -> CryptoPanicHttpClient:
    return CryptoPanicHttpClient(
        base_url="https://cryptopanic.com/api/v1/",
        api_key="test-key",
    )


@respx.mock
async def test_get_btc_news_parses_results_and_sends_filters(client: CryptoPanicHttpClient) -> None:
    route = respx.get("https://cryptopanic.com/api/v1/posts/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1,
                        "title": "Bitcoin hits new high",
                        "published_at": "2026-04-06T12:00:00Z",
                        "source": {"title": "CoinDesk", "domain": "coindesk.com"},
                        "url": "https://cryptopanic.com/news/1/click",
                    },
                    {
                        "id": 2,
                        "title": "Whale transfers 5000 BTC",
                        "published_at": "2026-04-06T11:00:00Z",
                        "source": {"title": "The Block", "domain": "theblock.co"},
                        "url": "https://cryptopanic.com/news/2/click",
                    },
                ]
            },
        )
    )

    items = await client.get_btc_news(limit=5)

    assert route.called
    params = route.calls.last.request.url.params
    assert params["auth_token"] == "test-key"
    assert params["currencies"] == "BTC"
    assert params["public"] == "true"
    assert len(items) == 2
    assert items[0].title == "Bitcoin hits new high"
    assert items[0].source == "CoinDesk"
    assert items[0].url.startswith("https://")
