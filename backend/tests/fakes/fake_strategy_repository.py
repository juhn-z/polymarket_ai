"""In-memory StrategyRepository fake."""
from __future__ import annotations

from dataclasses import replace

from app.domain.strategies import Strategy

_ACTIVE = {"pending", "executing", "active"}


class FakeStrategyRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Strategy] = {}
        self._next_id = 1

    async def save(self, strategy: Strategy) -> Strategy:
        if strategy.id is not None and strategy.id in self._by_id:
            self._by_id[strategy.id] = strategy
            return strategy
        assigned = replace(strategy, id=self._next_id)
        self._by_id[self._next_id] = assigned
        self._next_id += 1
        return assigned

    async def get_by_id(self, strategy_id: int) -> Strategy | None:
        return self._by_id.get(strategy_id)

    async def list_active(self) -> list[Strategy]:
        return [s for s in self._by_id.values() if s.status in _ACTIVE]

    async def list_all(self) -> list[Strategy]:
        return sorted(self._by_id.values(), key=lambda s: s.created_at, reverse=True)

    async def get_latest_for_market(self, market_id: int) -> Strategy | None:
        matches = [s for s in self._by_id.values() if s.market_id == market_id]
        if not matches:
            return None
        return max(matches, key=lambda s: s.created_at)
