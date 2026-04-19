"""Unit tests for MarketScanner event & price-band filtering."""
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
    *,
    condition_id: str = "0xabc",
    threshold: int = 66000,
    target_date: date = TARGET_DATE,
    yes_price: str = "0.50",
    volume: str = "50000",
) -> GammaMarket:
    return GammaMarket(
        condition_id=condition_id,
        yes_token_id=f"yes-{condition_id}",
        no_token_id=f"no-{condition_id}",
        question=f"Bitcoin above {threshold} on April 7?",
        price_threshold=threshold,
        target_date=target_date,
        yes_price=Decimal(yes_price),
        no_price=Decimal("1") - Decimal(yes_price),
        volume_24h=Decimal(volume),
    )


def _event(
    event_id: str = "evt-1",
    *,
    title: str = "Bitcoin above on April 7",
    active: bool = True,
) -> GammaEvent:
    return GammaEvent(id=event_id, slug="bitcoin-above-april-7", title=title, active=active)


def _scanner(events: list[GammaEvent], markets: dict[str, list[GammaMarket]]) -> MarketScanner:
    return MarketScanner(
        gamma=FakePolymarketGammaClient(events=events, markets=markets),
        repo=FakeMarketRepository(),
        clock=_clock,
    )


class TestMarketScanner:
    async def test_excludes_markets_below_35pct(self) -> None:
        scanner = _scanner(
            events=[_event()],
            markets={
                "evt-1": [
                    _market(condition_id="0xtoo_low", yes_price="0.20", volume="99999"),
                    _market(condition_id="0xok", yes_price="0.50", volume="15000"),
                ],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xok"

    async def test_excludes_markets_above_65pct(self) -> None:
        scanner = _scanner(
            events=[_event()],
            markets={
                "evt-1": [
                    _market(condition_id="0xtoo_high", yes_price="0.80", volume="99999"),
                    _market(condition_id="0xok", yes_price="0.50", volume="15000"),
                ],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xok"

    async def test_skips_inactive_events(self) -> None:
        scanner = _scanner(
            events=[
                _event("evt-inactive", active=False),
                _event("evt-active", active=True),
            ],
            markets={
                "evt-inactive": [_market(condition_id="0xinactive", yes_price="0.50", volume="99999")],
                "evt-active": [_market(condition_id="0xactive", yes_price="0.50", volume="15000")],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xactive"

    async def test_skips_events_not_matching_btc_above_pattern(self) -> None:
        scanner = _scanner(
            events=[
                _event("evt-other", title="Will ETH flip BTC by 2026?"),
                _event("evt-btc", title="Bitcoin above 66000 on April 7"),
            ],
            markets={
                "evt-other": [_market(condition_id="0xother", yes_price="0.50", volume="99999")],
                "evt-btc": [_market(condition_id="0xbtc", yes_price="0.50", volume="15000")],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xbtc"

    async def test_returns_none_when_no_candidates(self) -> None:
        scanner = _scanner(events=[], markets={})

        chosen = await scanner.scan_today()

        assert chosen is None

    async def test_aggregates_candidates_across_multiple_events(self) -> None:
        """When multiple matching events exist, all their markets compete in the final sort."""
        scanner = _scanner(
            events=[
                _event("evt-a", title="Bitcoin above 60000 on April 7"),
                _event("evt-b", title="Bitcoin above 70000 on April 7"),
            ],
            markets={
                "evt-a": [_market(condition_id="0xa", yes_price="0.55", volume="50000")],
                "evt-b": [_market(condition_id="0xb", yes_price="0.51", volume="20000")],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        # 0xb is closer to 0.5 (|0.51-0.5|=0.01 vs |0.55-0.5|=0.05).
        assert chosen.polymarket_condition_id == "0xb"
