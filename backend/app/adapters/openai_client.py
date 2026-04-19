"""HTTP adapter for OpenAI Chat Completions with Structured Outputs.

Uses the REST endpoint directly (not the SDK) so tests can mock with respx
against a concrete URL. Structured Outputs require the message ``content``
to be a JSON string matching the supplied schema.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

_CHAT_PATH = "/chat/completions"
_DEFAULT_TIMEOUT_SECONDS = 60.0
_DEFAULT_TEMPERATURE = 0.2
_DEFAULT_TOP_P = 0.9
_DEFAULT_MAX_TOKENS = 4096
_SCHEMA_NAME = "prediction"


class OpenAIHttpClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        temperature: float = _DEFAULT_TEMPERATURE,
        top_p: float = _DEFAULT_TOP_P,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def predict(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, Any],
        seed: int,
        model: str,
    ) -> dict[str, Any]:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": _SCHEMA_NAME,
                    "strict": True,
                    "schema": response_schema,
                },
            },
            "temperature": self._temperature,
            "top_p": self._top_p,
            "max_tokens": self._max_tokens,
            "seed": seed,
        }

        started = time.monotonic()
        response = await self._client.post(
            f"{self._base_url}{_CHAT_PATH}",
            json=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        response.raise_for_status()
        payload = response.json()

        try:
            content_str = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"OpenAI response missing choices/message/content: {exc}") from exc

        try:
            content = json.loads(content_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI response content is not valid JSON: {exc}") from exc

        tokens_used = int(payload.get("usage", {}).get("total_tokens", 0))
        return {"content": content, "tokens_used": tokens_used, "latency_ms": latency_ms}
