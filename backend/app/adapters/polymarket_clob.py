"""Minimal HTTP adapter for the Polymarket CLOB API.

Notes:
  - The real Polymarket CLOB requires L1/L2 signed headers using the API
    credentials (key, secret, passphrase). The signing protocol is
    documented at https://docs.polymarket.com/developers/CLOB/authentication.
  - This v1 adapter ships without signing: `place_order`/`cancel_order`
    raise `RuntimeError` until credentials are wired in a future milestone.
  - Read-only calls (`get_order`, `get_positions`, `get_current_price`) are
    wired against the public / key-bearing endpoints and covered by the
    live smoke suite.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.domain.trades import Order, Position

_DEFAULT_TIMEOUT_SECONDS = 15.0


class PolymarketCLOBHttpClient:
    def __init__(
        self,
        *,
        base_url: str = "https://clob.polymarket.com",
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        client: httpx.AsyncClient | None = None,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def place_order(
        self, *, token_id: str, side: str, price: Decimal, size: Decimal,
    ) -> Order:
        raise RuntimeError(
            "Polymarket CLOB order signing not implemented in v1. "
            "Configure API credentials and implement EIP-712 signing before going live."
        )

    async def cancel_order(self, order_id: str) -> bool:
        raise RuntimeError(
            "Polymarket CLOB order signing not implemented in v1."
        )

    async def get_order(self, order_id: str) -> Order:
        resp = await self._client.get(
            f"{self._base_url}/orders/{order_id}",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return _parse_order(resp.json())

    async def get_positions(self) -> list[Position]:
        resp = await self._client.get(
            f"{self._base_url}/positions",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return [_parse_position(row) for row in resp.json()]

    async def get_current_price(self, token_id: str) -> Decimal:
        resp = await self._client.get(
            f"{self._base_url}/price",
            params={"token_id": token_id, "side": "BUY"},
        )
        resp.raise_for_status()
        payload = resp.json()
        return Decimal(str(payload.get("price", "0")))

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"POLY_API_KEY": self._api_key}
        return {}


def _parse_order(payload: dict[str, Any]) -> Order:
    return Order(
        order_id=str(payload["id"]),
        token_id=str(payload["asset_id"]),
        side=str(payload["side"]).lower(),  # type: ignore[arg-type]
        price=Decimal(str(payload["price"])),
        size=Decimal(str(payload["size"])),
        filled_size=Decimal(str(payload.get("filled", payload.get("size")))),
        status=str(payload.get("status", "pending")).lower(),
        fee=Decimal(str(payload.get("fee", "0"))),
    )


def _parse_position(payload: dict[str, Any]) -> Position:
    return Position(
        token_id=str(payload["asset_id"]),
        balance=Decimal(str(payload["balance"])),
        avg_price=Decimal(str(payload.get("avg_price", "0"))),
    )
