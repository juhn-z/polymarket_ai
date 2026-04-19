"""Trade persistence interface."""
from __future__ import annotations

from typing import Protocol

from app.domain.trades import Trade


class TradeRepository(Protocol):
    async def save(self, trade: Trade) -> Trade: ...

    async def get_by_id(self, trade_id: int) -> Trade | None: ...

    async def list_active(self) -> list[Trade]: ...

    async def list_all(self) -> list[Trade]: ...

    async def list_for_strategy(self, strategy_id: int) -> list[Trade]: ...
