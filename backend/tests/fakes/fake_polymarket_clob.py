"""In-memory PolymarketCLOBClient fake."""
from __future__ import annotations

from decimal import Decimal

from app.domain.trades import Order, Position


class FakePolymarketCLOBClient:
    def __init__(self, prices: dict[str, Decimal] | None = None) -> None:
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._prices: dict[str, Decimal] = dict(prices) if prices else {}
        self._next_id = 1
        self.place_calls: list[dict] = []
        self.cancel_calls: list[str] = []

    def set_price(self, token_id: str, price: Decimal) -> None:
        self._prices[token_id] = price

    def set_order_filled(self, order_id: str, fill_price: Decimal | None = None) -> None:
        o = self._orders[order_id]
        price = fill_price if fill_price is not None else o.price
        self._orders[order_id] = Order(
            order_id=o.order_id,
            token_id=o.token_id,
            side=o.side,
            price=price,
            size=o.size,
            filled_size=o.size,
            status="filled",
            fee=o.fee,
        )

    async def place_order(
        self, *, token_id: str, side: str, price: Decimal, size: Decimal,
    ) -> Order:
        order_id = f"ord-{self._next_id}"
        self._next_id += 1
        self.place_calls.append(
            {"token_id": token_id, "side": side, "price": price, "size": size, "order_id": order_id}
        )
        # Default: fill immediately at requested price with 1% fee.
        order = Order(
            order_id=order_id,
            token_id=token_id,
            side=side,  # type: ignore[arg-type]
            price=price,
            size=size,
            filled_size=size,
            status="filled",
            fee=price * size * Decimal("0.01"),
        )
        self._orders[order_id] = order
        # Update position on buy / close on sell.
        if side == "buy":
            existing = self._positions.get(token_id)
            new_bal = (existing.balance if existing else Decimal("0")) + size
            self._positions[token_id] = Position(
                token_id=token_id, balance=new_bal, avg_price=price,
            )
        else:  # sell
            existing = self._positions.get(token_id)
            if existing is not None:
                remaining = existing.balance - size
                if remaining <= 0:
                    self._positions.pop(token_id, None)
                else:
                    self._positions[token_id] = Position(
                        token_id=token_id, balance=remaining, avg_price=existing.avg_price,
                    )
        return order

    async def get_order(self, order_id: str) -> Order:
        if order_id not in self._orders:
            raise LookupError(f"Order {order_id} not found")
        return self._orders[order_id]

    async def cancel_order(self, order_id: str) -> bool:
        self.cancel_calls.append(order_id)
        if order_id not in self._orders:
            return False
        self._orders[order_id] = Order(
            order_id=order_id,
            token_id=self._orders[order_id].token_id,
            side=self._orders[order_id].side,
            price=self._orders[order_id].price,
            size=self._orders[order_id].size,
            filled_size=self._orders[order_id].filled_size,
            status="cancelled",
            fee=self._orders[order_id].fee,
        )
        return True

    async def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    async def get_current_price(self, token_id: str) -> Decimal:
        return self._prices.get(token_id, Decimal("0.5"))
