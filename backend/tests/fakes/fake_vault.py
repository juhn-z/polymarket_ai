"""In-memory VaultClient fake — simulates PolyVault on-chain state."""
from __future__ import annotations

from decimal import Decimal

from app.domain.trades import TxReceipt


class FakeVaultClient:
    def __init__(
        self,
        *,
        total_assets: Decimal = Decimal("100000"),
        available_balance: Decimal = Decimal("100000"),
        share_price: Decimal = Decimal("1.0"),
    ) -> None:
        self._total_assets = total_assets
        self._available = available_balance
        self._share_price = share_price
        self._next_block = 1
        self.withdraw_calls: list[Decimal] = []
        self.deposit_calls: list[Decimal] = []

    async def total_assets(self) -> Decimal:
        return self._total_assets

    async def share_price(self) -> Decimal:
        return self._share_price

    async def available_balance(self) -> Decimal:
        return self._available

    async def withdraw_to_strategy(self, amount: Decimal) -> TxReceipt:
        if amount > self._available:
            raise ValueError(f"insufficient vault balance: {amount} > {self._available}")
        self._available -= amount
        self.withdraw_calls.append(amount)
        return self._receipt()

    async def deposit_from_strategy(self, amount: Decimal) -> TxReceipt:
        self._available += amount
        self.deposit_calls.append(amount)
        return self._receipt()

    def _receipt(self) -> TxReceipt:
        tx_hash = f"0x{self._next_block:064x}"
        receipt = TxReceipt(tx_hash=tx_hash, block_number=self._next_block, status=1)
        self._next_block += 1
        return receipt
