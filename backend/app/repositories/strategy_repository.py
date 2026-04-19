"""Strategy persistence interface."""
from __future__ import annotations

from typing import Protocol

from app.domain.strategies import Strategy


class StrategyRepository(Protocol):
    async def save(self, strategy: Strategy) -> Strategy: ...

    async def get_by_id(self, strategy_id: int) -> Strategy | None: ...

    async def list_active(self) -> list[Strategy]: ...

    async def list_all(self) -> list[Strategy]: ...

    async def get_latest_for_market(self, market_id: int) -> Strategy | None: ...
