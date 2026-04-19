"""Domain types for Polymarket market data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class GammaEvent:
    id: str
    slug: str
    title: str
    active: bool


@dataclass(frozen=True, slots=True)
class GammaMarket:
    """Raw market snapshot from the Polymarket Gamma API."""
    condition_id: str
    yes_token_id: str
    no_token_id: str
    question: str
    price_threshold: int
    target_date: date
    yes_price: Decimal
    no_price: Decimal
    volume_24h: Decimal


MarketStatus = Literal["active", "resolved", "expired"]
MarketResolution = Literal["yes", "no"]


@dataclass
class Market:
    """Persisted snapshot of a Polymarket market our scanner has selected.

    `scan_date` is the UTC date on which the scanner ran and is the
    idempotency key: at most one Market row per scan_date. `target_date`
    is when the underlying Polymarket market resolves (scan_date + 2).
    """
    polymarket_condition_id: str
    polymarket_token_id: str  # the Yes token id (the side AI bets on by default)
    event_slug: str
    question: str
    price_threshold: int
    scan_date: date
    target_date: date
    current_yes_price: Decimal
    current_no_price: Decimal
    selected_at: datetime
    status: MarketStatus = "active"
    resolution: MarketResolution | None = None
    id: int | None = None

    @classmethod
    def from_gamma(
        cls,
        gamma_market: GammaMarket,
        *,
        event_slug: str,
        scan_date: date,
        selected_at: datetime | None = None,
    ) -> "Market":
        return cls(
            polymarket_condition_id=gamma_market.condition_id,
            polymarket_token_id=gamma_market.yes_token_id,
            event_slug=event_slug,
            question=gamma_market.question,
            price_threshold=gamma_market.price_threshold,
            scan_date=scan_date,
            target_date=gamma_market.target_date,
            current_yes_price=gamma_market.yes_price,
            current_no_price=gamma_market.no_price,
            selected_at=selected_at or datetime.now(timezone.utc),
        )
