"""HTTP adapter for the alternative.me Fear & Greed index."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.domain.sentiment import FearGreedPoint

_DEFAULT_TIMEOUT_SECONDS = 10.0


class FearGreedHttpClient:
    def __init__(
        self,
        base_url: str = "https://api.alternative.me/fng/",
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_index(self, days: int = 7) -> list[FearGreedPoint]:
        response = await self._client.get(self._base_url, params={"limit": days})
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", [])
        return [_parse(row) for row in rows]


def _parse(row: dict) -> FearGreedPoint:
    return FearGreedPoint(
        value=int(row["value"]),
        label=row["value_classification"],
        at=datetime.fromtimestamp(int(row["timestamp"]), tz=timezone.utc).date(),
    )
