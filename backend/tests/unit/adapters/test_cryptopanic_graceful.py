"""CryptoPanicHttpClient must skip the network call when no API key is configured."""
from __future__ import annotations

import httpx
import pytest

from app.adapters.cryptopanic import CryptoPanicHttpClient


@pytest.mark.asyncio
async def test_returns_empty_list_when_api_key_missing():
    """No HTTP call should be made; result is [] so the aggregator can degrade gracefully."""
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        calls.append(str(request.url))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    client = CryptoPanicHttpClient(api_key="", client=httpx.AsyncClient(transport=transport))
    try:
        result = await client.get_btc_news(limit=5)
    finally:
        await client.aclose()

    assert result == []
    assert calls == []  # zero network traffic when key missing


@pytest.mark.asyncio
async def test_calls_api_when_key_present():
    """With a key, behavior is unchanged — network call is made."""
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    client = CryptoPanicHttpClient(api_key="abc123", client=httpx.AsyncClient(transport=transport))
    try:
        await client.get_btc_news(limit=5)
    finally:
        await client.aclose()

    assert len(calls) == 1
    assert "auth_token=abc123" in calls[0]
