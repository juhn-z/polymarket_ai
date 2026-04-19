"""In-memory MarketRepository fake."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from app.domain.markets import Market


class FakeMarketRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Market] = {}
        self._next_id = 1

    async def save(self, market: Market) -> Market:
        if market.id is not None and market.id in self._by_id:
            self._by_id[market.id] = market
            return market
        assigned = replace(market, id=self._next_id)
        self._by_id[self._next_id] = assigned
        self._next_id += 1
        return assigned

    async def get_by_condition_id(self, condition_id: str) -> Market | None:
        for m in self._by_id.values():
            if m.polymarket_condition_id == condition_id:
                return m
        return None

    async def get_by_scan_date(self, scan_date: date) -> Market | None:
        matches = [m for m in self._by_id.values() if m.scan_date == scan_date]
        if not matches:
            return None
        return max(matches, key=lambda m: m.selected_at)

    async def get_latest(self) -> Market | None:
        if not self._by_id:
            return None
        return max(self._by_id.values(), key=lambda m: m.selected_at)

    async def list_all(self) -> list[Market]:
        return list(self._by_id.values())
