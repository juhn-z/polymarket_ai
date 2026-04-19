"""In-memory TradeRepository fake."""
from __future__ import annotations

from dataclasses import replace

from app.domain.trades import Trade

_ACTIVE = {"pending", "partial"}


class FakeTradeRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Trade] = {}
        self._next_id = 1

    async def save(self, trade: Trade) -> Trade:
        if trade.id is not None and trade.id in self._by_id:
            self._by_id[trade.id] = trade
            return trade
        assigned = replace(trade, id=self._next_id)
        self._by_id[self._next_id] = assigned
        self._next_id += 1
        return assigned

    async def get_by_id(self, trade_id: int) -> Trade | None:
        return self._by_id.get(trade_id)

    async def list_active(self) -> list[Trade]:
        return [t for t in self._by_id.values() if t.status in _ACTIVE]

    async def list_all(self) -> list[Trade]:
        return sorted(self._by_id.values(), key=lambda t: t.created_at, reverse=True)

    async def list_for_strategy(self, strategy_id: int) -> list[Trade]:
        return [t for t in self._by_id.values() if t.strategy_id == strategy_id]
