"""OFAC SDN crypto-address screening (Section 10.4 — OFAC SDN crypto addresses)."""
from __future__ import annotations

from app.store import KeyValueStore

_OFAC_WALLET_KEY_PREFIX = "ofac_wallet:"


class OFACWalletScreener:
    """Exact-match lookup against OFAC SDN-published crypto addresses.

    Addresses are stored as individual keys so a daily Celery refresh (list-sync
    domain) can update entries without rebuilding a large structure.
    """

    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def load(self, addresses: list[str]) -> None:
        for address in addresses:
            await self._store.set(_OFAC_WALLET_KEY_PREFIX + address.lower(), "1")

    async def lookup(self, address: str) -> bool:
        return await self._store.exists(_OFAC_WALLET_KEY_PREFIX + address.lower())
