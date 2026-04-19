"""Prediction persistence interface."""
from __future__ import annotations

from typing import Protocol

from app.domain.predictions import Prediction


class PredictionRepository(Protocol):
    async def save(self, prediction: Prediction) -> Prediction: ...

    async def get_by_id(self, prediction_id: int) -> Prediction | None: ...

    async def get_latest_for_market(self, market_id: int) -> Prediction | None: ...

    async def get_latest(self) -> Prediction | None: ...

    async def list_all(self) -> list[Prediction]: ...
