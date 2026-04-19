"""Scanner must persist its chosen market via repository."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.markets import GammaEvent, GammaMarket
from app.services.market_scanner import MarketScanner
from tests.fakes.fake_market_repository import FakeMarketRepository
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient


def _market(condition_id: str = "0xabc", yes_price: str = "0.50", volume: str = "1000") -> GammaMarket:
    return GammaMarket(
        condition_id=condition_id,
        yes_token_id=f"yes-{condition_id}",
        no_token_id=f"no-{condition_id}",
        question="Bitcoin above 66000 on April 6?",
        price_threshold=66000,
        target_date=date(2026, 4, 6),
        yes_price=Decimal(yes_price),
        no_price=Decimal("1") - Decimal(yes_price),
        volume_24h=Decimal(volume),
    )


def _event(event_id: str = "evt-1") -> GammaEvent:
    return GammaEvent(id=event_id, slug="bitcoin-above", title="Bitcoin above 66000 on April 6", active=True)


class TestMarketScannerPersistence:
    async def test_scan_today_saves_chosen_market(self) -> None:
        gamma = FakePolymarketGammaClient(
            events=[_event()],
            markets={"evt-1": [_market(condition_id="0xchosen")]},
        )
        repo = FakeMarketRepository()
        scanner = MarketScanner(gamma=gamma, repo=repo)

        chosen = await scanner.scan_today()

        assert chosen is not None
        saved = await repo.get_by_condition_id("0xchosen")
        assert saved is not None
        assert saved.polymarket_condition_id == "0xchosen"
        assert saved.price_threshold == 66000
        assert saved.status == "active"

    async def test_scan_today_does_not_save_when_no_candidate(self) -> None:
        gamma = FakePolymarketGammaClient(events=[], markets={})
        repo = FakeMarketRepository()
        scanner = MarketScanner(gamma=gamma, repo=repo)

        chosen = await scanner.scan_today()

        assert chosen is None
        assert await repo.list_all() == []

    async def test_scan_today_returns_existing_market_when_already_saved_today(self) -> None:
        """Re-running scanner same day should be idempotent — return existing, not duplicate."""
        gamma = FakePolymarketGammaClient(
            events=[_event()],
            markets={"evt-1": [_market(condition_id="0xtoday")]},
        )
        repo = FakeMarketRepository()
        scanner = MarketScanner(gamma=gamma, repo=repo)

        first = await scanner.scan_today()
        second = await scanner.scan_today()

        assert first is not None and second is not None
        assert first.id == second.id
        all_markets = await repo.list_all()
        assert len(all_markets) == 1
