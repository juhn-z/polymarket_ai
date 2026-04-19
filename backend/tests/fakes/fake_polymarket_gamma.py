"""In-memory fake of PolymarketGammaClient for tests."""
from __future__ import annotations

from collections.abc import Mapping

from app.domain.markets import GammaEvent, GammaMarket


class FakePolymarketGammaClient:
    def __init__(
        self,
        events: list[GammaEvent],
        markets: Mapping[str, list[GammaMarket]],
    ) -> None:
        self._events = list(events)
        self._markets = {k: list(v) for k, v in markets.items()}
        self.search_calls: list[str] = []
        self.market_calls: list[str] = []

    async def search_events(self, tag: str) -> list[GammaEvent]:
        self.search_calls.append(tag)
        return list(self._events)

    async def get_event_markets(self, event_id: str) -> list[GammaMarket]:
        self.market_calls.append(event_id)
        return list(self._markets.get(event_id, []))
