"""Daily Polymarket BTC market scanner."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from app.adapters.protocols import PolymarketGammaClient
from app.domain.markets import GammaEvent, GammaMarket, Market
from app.repositories.market_repository import MarketRepository

_MIN_PROBABILITY = Decimal("0.35")
_MAX_PROBABILITY = Decimal("0.65")
_BTC_ABOVE_PATTERN = re.compile(r"bitcoin\s+above", re.IGNORECASE)
_BITCOIN_TAG = "bitcoin"


class MarketScanner:
    """Selects the best Polymarket BTC prediction market for AI trading.

    Strategy: among active "Bitcoin above ___" events, choose the market
    whose Yes price sits inside [0.35, 0.65] (highest informational value)
    and has the largest 24h volume (best liquidity for execution).

    Persistence is idempotent: re-running on the same `target_date` returns
    the previously-saved Market instead of inserting a duplicate.
    """

    def __init__(self, gamma: PolymarketGammaClient, repo: MarketRepository) -> None:
        self._gamma = gamma
        self._repo = repo

    async def scan_today(self) -> Market | None:
        chosen, event = await self._select_best()
        if chosen is None or event is None:
            return None

        existing = await self._repo.get_latest_for_date(chosen.target_date)
        if existing is not None and existing.polymarket_condition_id == chosen.condition_id:
            return existing

        market = Market.from_gamma(
            chosen,
            event_slug=event.slug,
            selected_at=datetime.now(timezone.utc),
        )
        return await self._repo.save(market)

    async def _select_best(self) -> tuple[GammaMarket | None, GammaEvent | None]:
        events = await self._gamma.search_events(tag=_BITCOIN_TAG)
        candidates: list[tuple[GammaMarket, GammaEvent]] = []
        for event in events:
            if not self._is_eligible_event(event):
                continue
            markets = await self._gamma.get_event_markets(event.id)
            for m in markets:
                if self._is_in_band(m):
                    candidates.append((m, event))

        if not candidates:
            return None, None
        best_market, best_event = max(candidates, key=lambda pair: pair[0].volume_24h)
        return best_market, best_event

    @staticmethod
    def _is_eligible_event(event: GammaEvent) -> bool:
        return event.active and bool(_BTC_ABOVE_PATTERN.search(event.title))

    @staticmethod
    def _is_in_band(market: GammaMarket) -> bool:
        return _MIN_PROBABILITY <= market.yes_price <= _MAX_PROBABILITY
