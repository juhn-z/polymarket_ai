"""In-memory OpenAIClient fake. Returns a canned response dict."""
from __future__ import annotations

from typing import Any


class FakeOpenAIClient:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        tokens_used: int = 1234,
        latency_ms: int = 42,
    ) -> None:
        self._response = response or {}
        self._tokens_used = tokens_used
        self._latency_ms = latency_ms
        self.calls: list[dict[str, Any]] = []

    async def predict(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, Any],
        seed: int,
        model: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "response_schema": response_schema,
                "seed": seed,
                "model": model,
            }
        )
        return {
            "content": self._response,
            "tokens_used": self._tokens_used,
            "latency_ms": self._latency_ms,
        }
