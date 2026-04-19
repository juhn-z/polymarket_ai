"""Protocol interfaces for external services. Service code depends only on these."""
from __future__ import annotations

from typing import Protocol

from app.domain.markets import GammaEvent, GammaMarket


class PolymarketGammaClient(Protocol):
    async def search_events(self, tag: str) -> list[GammaEvent]: ...

    async def get_event_markets(self, event_id: str) -> list[GammaMarket]: ...
