"""HTTP adapter for the CryptoPanic news API."""
from __future__ import annotations

from datetime import datetime

import httpx

from app.domain.sentiment import NewsItem

_DEFAULT_TIMEOUT_SECONDS = 10.0


class CryptoPanicHttpClient:
    def __init__(
        self,
        base_url: str = "https://cryptopanic.com/api/v1/",
        api_key: str = "",
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_btc_news(self, limit: int = 10) -> list[NewsItem]:
        response = await self._client.get(
            f"{self._base_url}posts/",
            params={
                "auth_token": self._api_key,
                "currencies": "BTC",
                "public": "true",
            },
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results", [])[:limit]
        return [_parse(row) for row in rows]


def _parse(row: dict) -> NewsItem:
    return NewsItem(
        id=int(row["id"]),
        title=row["title"],
        source=row.get("source", {}).get("title", "unknown"),
        url=row["url"],
        published_at=datetime.fromisoformat(row["published_at"].replace("Z", "+00:00")),
    )
