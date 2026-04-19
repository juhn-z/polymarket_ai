"""web3.py adapter for the PolyVault contract on Polygon.

Read paths (``total_assets``, ``share_price``, ``available_balance``) are
implemented via ``eth_call`` and work out of the box. Write paths
(``withdraw_to_strategy``, ``deposit_from_strategy``) are only safe once the
admin EOA has the ``STRATEGIST_ROLE`` granted on the deployed vault. They
sign and broadcast real transactions — covered by the Hardhat fork live
test, skipped from default CI.
"""
from __future__ import annotations

from decimal import Decimal

from eth_account import Account
from web3 import AsyncHTTPProvider, AsyncWeb3

from app.domain.trades import TxReceipt

USDC_DECIMALS = 6
SHARE_DECIMALS = 18
_USDC_SCALE = Decimal(10) ** USDC_DECIMALS

_VAULT_ABI = [
    {"name": "totalAssets", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "availableBalance", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "convertToAssets", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "uint256", "name": "shares"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "withdrawToStrategy", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"type": "uint256", "name": "amount"}], "outputs": []},
    {"name": "depositFromStrategy", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"type": "uint256", "name": "amount"}], "outputs": []},
]


class VaultChainClient:
    def __init__(
        self,
        *,
        rpc_url: str,
        vault_address: str,
        admin_private_key: str,
    ) -> None:
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self._address = AsyncWeb3.to_checksum_address(vault_address)
        if admin_private_key and admin_private_key != "0x" + "0" * 64:
            self._account = Account.from_key(admin_private_key)
        else:
            self._account = None
        self._contract = self._w3.eth.contract(address=self._address, abi=_VAULT_ABI)

    async def total_assets(self) -> Decimal:
        raw = await self._contract.functions.totalAssets().call()
        return Decimal(raw) / _USDC_SCALE

    async def available_balance(self) -> Decimal:
        raw = await self._contract.functions.availableBalance().call()
        return Decimal(raw) / _USDC_SCALE

    async def share_price(self) -> Decimal:
        # convertToAssets(1e18) → USDC-for-one-share (6 decimals)
        one_share = 10 ** SHARE_DECIMALS
        raw = await self._contract.functions.convertToAssets(one_share).call()
        return Decimal(raw) / _USDC_SCALE

    async def withdraw_to_strategy(self, amount: Decimal) -> TxReceipt:
        return await self._send_tx("withdrawToStrategy", amount)

    async def deposit_from_strategy(self, amount: Decimal) -> TxReceipt:
        return await self._send_tx("depositFromStrategy", amount)

    async def _send_tx(self, fn_name: str, amount: Decimal) -> TxReceipt:
        if self._account is None:
            raise RuntimeError(
                "VaultChainClient has no signing key configured; set ADMIN_PRIVATE_KEY"
            )
        amount_wei = int(amount * _USDC_SCALE)
        fn = getattr(self._contract.functions, fn_name)(amount_wei)
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        gas = await fn.estimate_gas({"from": self._account.address})
        tx = await fn.build_transaction(
            {
                "from": self._account.address,
                "nonce": nonce,
                "gas": gas,
                "maxFeePerGas": await self._w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": await self._w3.eth.gas_price,
                "chainId": await self._w3.eth.chain_id,
            }
        )
        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash)
        return TxReceipt(
            tx_hash=tx_hash.hex(),
            block_number=int(receipt["blockNumber"]),
            status=int(receipt["status"]),
        )
