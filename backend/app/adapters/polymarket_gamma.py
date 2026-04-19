"""HTTP adapter for the Polymarket Gamma API."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.domain.markets import GammaEvent, GammaMarket

_THRESHOLD_PATTERN = re.compile(r"\$?(\d{1,3}(?:,\d{3})+|\d+)", re.IGNORECASE)
_DEFAULT_TIMEOUT_SECONDS = 15.0


class PolymarketGammaHttpClient:
    """Real Polymarket Gamma API client.

    Schema reference: https://gamma-api.polymarket.com/events
    Polymarket returns ``outcomes``, ``outcomePrices`` and ``clobTokenIds`` as
    JSON-encoded strings inside the JSON document — these need a second decode.
    """

    def __init__(
        self,
        base_url: str = "https://gamma-api.polymarket.com",
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_events(self, tag: str) -> list[GammaEvent]:
        response = await self._client.get(
            f"{self._base_url}/events",
            params={"tag_slug": tag, "active": "true", "closed": "false", "limit": 100},
        )
        response.raise_for_status()
        payload = response.json()
        events = (_parse_event(item) for item in payload)
        return [e for e in events if e.active]

    async def get_event_markets(self, event_id: str) -> list[GammaMarket]:
        response = await self._client.get(f"{self._base_url}/events/{event_id}")
        response.raise_for_status()
        payload = response.json()
        markets = []
        for raw_market in payload.get("markets", []):
            parsed = _try_parse_market(raw_market)
            if parsed is not None:
                markets.append(parsed)
        return markets


def _parse_event(payload: dict[str, Any]) -> GammaEvent:
    return GammaEvent(
        id=str(payload["id"]),
        slug=payload["slug"],
        title=payload["title"],
        active=bool(payload.get("active", False)) and not bool(payload.get("closed", False)),
    )


def _try_parse_market(payload: dict[str, Any]) -> GammaMarket | None:
    try:
        question = payload["question"]
        threshold = _extract_threshold(question)
        if threshold is None:
            return None
        outcome_prices = _decode_string_array(payload.get("outcomePrices"))
        if outcome_prices is None or len(outcome_prices) != 2:
            return None
        token_ids = _decode_string_array(payload.get("clobTokenIds"))
        if token_ids is None or len(token_ids) != 2:
            return None
        end_date_iso = payload["endDate"]
        target = _parse_iso_date(end_date_iso)
        yes_price = Decimal(outcome_prices[0])
        no_price = Decimal(outcome_prices[1])
        volume = Decimal(str(payload.get("volume", "0")))
    except (KeyError, ValueError, InvalidOperation, TypeError):
        return None

    return GammaMarket(
        condition_id=payload["conditionId"],
        yes_token_id=token_ids[0],
        no_token_id=token_ids[1],
        question=question,
        price_threshold=threshold,
        target_date=target,
        yes_price=yes_price,
        no_price=no_price,
        volume_24h=volume,
    )


def _extract_threshold(question: str) -> int | None:
    """Pull the dollar threshold out of a question like 'Bitcoin above $70,000 on ...'."""
    match = _THRESHOLD_PATTERN.search(question)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        value = int(raw)
    except ValueError:
        return None
    # Sanity: BTC thresholds are at least 4 digits.
    if value < 1000:
        return None
    return value


def _decode_string_array(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    return None


def _parse_iso_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
