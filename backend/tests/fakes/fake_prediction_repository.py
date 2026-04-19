"""In-memory PredictionRepository fake."""
from __future__ import annotations

from dataclasses import replace

from app.domain.predictions import Prediction


class FakePredictionRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Prediction] = {}
        self._next_id = 1

    async def save(self, prediction: Prediction) -> Prediction:
        if prediction.id is not None and prediction.id in self._by_id:
            self._by_id[prediction.id] = prediction
            return prediction
        assigned = replace(prediction, id=self._next_id)
        self._by_id[self._next_id] = assigned
        self._next_id += 1
        return assigned

    async def get_by_id(self, prediction_id: int) -> Prediction | None:
        return self._by_id.get(prediction_id)

    async def get_latest_for_market(self, market_id: int) -> Prediction | None:
        matches = [p for p in self._by_id.values() if p.market_id == market_id]
        if not matches:
            return None
        return max(matches, key=lambda p: p.created_at)

    async def get_latest(self) -> Prediction | None:
        if not self._by_id:
            return None
        return max(self._by_id.values(), key=lambda p: p.created_at)

    async def list_all(self) -> list[Prediction]:
        return sorted(self._by_id.values(), key=lambda p: p.created_at, reverse=True)
