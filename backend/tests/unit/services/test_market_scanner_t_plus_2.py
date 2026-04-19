"""PRD update: scanner selects markets resolving T+2 with stricter filters/sort."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.domain.markets import GammaEvent, GammaMarket
from app.services.market_scanner import MarketScanner
from tests.fakes.fake_market_repository import FakeMarketRepository
from tests.fakes.fake_polymarket_gamma import FakePolymarketGammaClient

MIN_VOLUME = Decimal("10000")

# Scan clock is fixed so tests are deterministic.
SCAN_AT = datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc)
SCAN_DATE = SCAN_AT.date()  # 2026-04-05
TARGET_DATE = SCAN_DATE + timedelta(days=2)  # 2026-04-07


def _fixed_clock():
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


def _event(event_id: str = "evt-1") -> GammaEvent:
    return GammaEvent(id=event_id, slug="bitcoin-above-april-7", title="Bitcoin above 66000 on April 7", active=True)


def _scanner(events, markets) -> MarketScanner:
    return MarketScanner(
        gamma=FakePolymarketGammaClient(events=events, markets=markets),
        repo=FakeMarketRepository(),
        clock=_fixed_clock,
    )


class TestTPlusTwoSelection:
    async def test_excludes_markets_not_resolving_exactly_two_days_after_scan(self) -> None:
        scanner = _scanner(
            events=[_event()],
            markets={
                "evt-1": [
                    _market(
                        condition_id="0xtoday",
                        target_date=SCAN_DATE,  # resolves today -> excluded
                        volume="999999",
                    ),
                    _market(
                        condition_id="0xtomorrow",
                        target_date=SCAN_DATE + timedelta(days=1),
                        volume="999999",
                    ),
                    _market(
                        condition_id="0xt_plus_two",
                        target_date=TARGET_DATE,
                        volume="50000",
                    ),
                    _market(
                        condition_id="0xt_plus_three",
                        target_date=SCAN_DATE + timedelta(days=3),
                        volume="999999",
                    ),
                ],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xt_plus_two"
        assert chosen.target_date == TARGET_DATE


class TestMinimumVolumeFilter:
    async def test_excludes_markets_below_10k_volume(self) -> None:
        scanner = _scanner(
            events=[_event()],
            markets={
                "evt-1": [
                    _market(condition_id="0xlow", volume="9999"),
                    _market(condition_id="0xok", volume="15000"),
                ],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xok"

    async def test_returns_none_when_all_markets_below_volume_floor(self) -> None:
        scanner = _scanner(
            events=[_event()],
            markets={"evt-1": [_market(condition_id="0xonly", volume="500")]},
        )

        assert await scanner.scan_today() is None


class TestClosestToFiftyPctSort:
    async def test_chooses_market_closest_to_50pct_over_higher_volume_further_out(self) -> None:
        """Sort priority 1 beats priority 2: closeness to 50% outweighs liquidity."""
        scanner = _scanner(
            events=[_event()],
            markets={
                "evt-1": [
                    # closest to 50% but lower volume (still above 10k floor)
                    _market(condition_id="0xtight", yes_price="0.51", volume="11000"),
                    # further from 50% but much higher volume
                    _market(condition_id="0xloose", yes_price="0.40", volume="500000"),
                ],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xtight"

    async def test_ties_broken_by_volume_desc(self) -> None:
        """Same distance from 0.5 (symmetric around midpoint) → higher volume wins."""
        scanner = _scanner(
            events=[_event()],
            markets={
                "evt-1": [
                    _market(condition_id="0xa", yes_price="0.48", volume="20000"),
                    _market(condition_id="0xb", yes_price="0.52", volume="30000"),
                ],
            },
        )

        chosen = await scanner.scan_today()

        assert chosen is not None
        assert chosen.polymarket_condition_id == "0xb"


class TestScanDateIdempotency:
    async def test_idempotency_key_is_scan_date_not_target_date(self) -> None:
        """Re-running the scanner on the same UTC day returns the existing record
        even if the fake gamma client now returns a different winner."""
        repo = FakeMarketRepository()
        gamma = FakePolymarketGammaClient(
            events=[_event()],
            markets={"evt-1": [_market(condition_id="0xfirst", volume="15000")]},
        )
        scanner = MarketScanner(gamma=gamma, repo=repo, clock=_fixed_clock)

        first = await scanner.scan_today()
        assert first is not None

        # Swap the gamma data entirely — a fresh scan would now pick 0xsecond.
        gamma._markets = {  # type: ignore[attr-defined]
            "evt-1": [_market(condition_id="0xsecond", volume="50000")],
        }

        second = await scanner.scan_today()

        assert second is not None
        assert second.polymarket_condition_id == "0xfirst"
        assert second.id == first.id
        assert len(await repo.list_all()) == 1
