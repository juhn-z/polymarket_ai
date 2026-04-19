"""In-memory fakes for FearGreedClient and NewsClient."""
from __future__ import annotations

from app.domain.sentiment import FearGreedPoint, NewsItem


class FakeFearGreedClient:
    def __init__(self, points: list[FearGreedPoint] | None = None) -> None:
        self._points = list(points) if points else []
        self.calls: list[int] = []

    async def get_index(self, days: int = 7) -> list[FearGreedPoint]:
        self.calls.append(days)
        return list(self._points[:days])


class FakeNewsClient:
    def __init__(self, items: list[NewsItem] | None = None) -> None:
        self._items = list(items) if items else []
        self.calls: list[int] = []

    async def get_btc_news(self, limit: int = 10) -> list[NewsItem]:
        self.calls.append(limit)
        return list(self._items[:limit])
