"""Daily Polymarket BTC market scanner (PRD §3.1)."""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.adapters.protocols import PolymarketGammaClient
from app.domain.markets import GammaEvent, GammaMarket, Market
from app.repositories.market_repository import MarketRepository

_MIN_PROBABILITY = Decimal("0.35")
_MAX_PROBABILITY = Decimal("0.65")
_MIN_VOLUME_24H = Decimal("10000")
_TARGET_OFFSET = timedelta(days=2)
_BTC_ABOVE_PATTERN = re.compile(r"bitcoin\s+above", re.IGNORECASE)
_BITCOIN_TAG = "bitcoin"
_MIDPOINT = Decimal("0.5")

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketScanner:
    """Selects the best Polymarket BTC prediction market for AI trading.

    Selection rules (PRD §3.1):
      1. target_date = scan_date + 2 days
      2. Event must be active and title contains "Bitcoin above"
      3. Market's own target_date must equal scan_date + 2
      4. Yes price ∈ [0.35, 0.65]
      5. 24h volume ≥ $10,000
      6. Sort: primary = |yes_price − 0.5| ascending (closest to 50% first)
               secondary = volume descending

    Idempotency: at most one Market row per scan_date. Re-runs on the same
    UTC day return the existing record.
    """

    def __init__(
        self,
        gamma: PolymarketGammaClient,
        repo: MarketRepository,
        clock: Clock = _utc_now,
    ) -> None:
        self._gamma = gamma
        self._repo = repo
        self._clock = clock

    async def scan_today(self) -> Market | None:
        now = self._clock()
        scan_date = now.date()
        target_date = scan_date + _TARGET_OFFSET

        existing = await self._repo.get_by_scan_date(scan_date)
        if existing is not None:
            return existing

        chosen, event = await self._select_best(target_date=target_date)
        if chosen is None or event is None:
            return None

        market = Market.from_gamma(
            chosen,
            event_slug=event.slug,
            scan_date=scan_date,
            selected_at=now,
        )
        return await self._repo.save(market)

    async def _select_best(self, *, target_date) -> tuple[GammaMarket | None, GammaEvent | None]:
        events = await self._gamma.search_events(tag=_BITCOIN_TAG)
        candidates: list[tuple[GammaMarket, GammaEvent]] = []
        for event in events:
            if not self._is_eligible_event(event):
                continue
            markets = await self._gamma.get_event_markets(event.id)
            for m in markets:
                if self._is_eligible_market(m, target_date=target_date):
                    candidates.append((m, event))

        if not candidates:
            return None, None

        best_market, best_event = min(candidates, key=_sort_key)
        return best_market, best_event

    @staticmethod
    def _is_eligible_event(event: GammaEvent) -> bool:
        return event.active and bool(_BTC_ABOVE_PATTERN.search(event.title))

    @staticmethod
    def _is_eligible_market(market: GammaMarket, *, target_date) -> bool:
        return (
            market.target_date == target_date
            and _MIN_PROBABILITY <= market.yes_price <= _MAX_PROBABILITY
            and market.volume_24h >= _MIN_VOLUME_24H
        )


def _sort_key(pair: tuple[GammaMarket, GammaEvent]) -> tuple[Decimal, Decimal]:
    market, _event = pair
    distance_from_midpoint = abs(market.yes_price - _MIDPOINT)
    # Negate volume so that min() treats higher volume as better (secondary key).
    return (distance_from_midpoint, -market.volume_24h)
