"""Scanner must persist its chosen market via repository."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.domain.markets import GammaEvent, GammaMarket
from app.services.market_scanner import MarketScanner
from tests.fakes.fake_market_repository import FakeMarketRepository
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient

SCAN_AT = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
TARGET_DATE = SCAN_AT.date() + timedelta(days=2)


def _clock():
    return SCAN_AT


def _market(
    condition_id: str = "0xabc",
    yes_price: str = "0.50",
    volume: str = "50000",
) -> GammaMarket:
    return GammaMarket(
        condition_id=condition_id,
        yes_token_id=f"yes-{condition_id}",
        no_token_id=f"no-{condition_id}",
        question="Bitcoin above 66000 on April 7?",
        price_threshold=66000,
        target_date=TARGET_DATE,
        yes_price=Decimal(yes_price),
        no_price=Decimal("1") - Decimal(yes_price),
        volume_24h=Decimal(volume),
    )


def _event(event_id: str = "evt-1") -> GammaEvent:
    return GammaEvent(id=event_id, slug="bitcoin-above", title="Bitcoin above 66000 on April 7", active=True)


class TestMarketScannerPersistence:
    async def test_scan_today_saves_chosen_market(self) -> None:
        gamma = FakePolymarketGammaClient(
            events=[_event()],
            markets={"evt-1": [_market(condition_id="0xchosen")]},
        )
        repo = FakeMarketRepository()
        scanner = MarketScanner(gamma=gamma, repo=repo, clock=_clock)

        chosen = await scanner.scan_today()

        assert chosen is not None
        saved = await repo.get_by_condition_id("0xchosen")
        assert saved is not None
        assert saved.polymarket_condition_id == "0xchosen"
        assert saved.price_threshold == 66000
        assert saved.status == "active"
        assert saved.scan_date == SCAN_AT.date()
        assert saved.target_date == TARGET_DATE

    async def test_scan_today_does_not_save_when_no_candidate(self) -> None:
        gamma = FakePolymarketGammaClient(events=[], markets={})
        repo = FakeMarketRepository()
        scanner = MarketScanner(gamma=gamma, repo=repo, clock=_clock)

        chosen = await scanner.scan_today()

        assert chosen is None
        assert await repo.list_all() == []
