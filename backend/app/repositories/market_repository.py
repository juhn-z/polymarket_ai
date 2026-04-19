"""Market persistence interface."""
from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.markets import Market


class MarketRepository(Protocol):
    async def save(self, market: Market) -> Market: ...

    async def get_by_condition_id(self, condition_id: str) -> Market | None: ...

    async def get_latest_for_date(self, target: date) -> Market | None: ...

    async def get_latest(self) -> Market | None: ...

    async def list_all(self) -> list[Market]: ...
