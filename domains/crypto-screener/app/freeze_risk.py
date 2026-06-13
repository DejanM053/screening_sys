"""Freeze-risk register — Redis set of recently-flagged wallets (Section 11.4).

If Tether/Circle subsequently freezes an address that was in this register,
the platform has a documented prior-screening record demonstrating it
identified the risk before the freeze.
"""
from __future__ import annotations

from app.config import settings
from app.store import KeyValueStore

_REGISTER_KEY_PREFIX = "freeze_risk:"


class FreezeRiskRegister:
    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def update_register(self, address: str, has_flag: bool) -> None:
        if not has_flag:
            return
        await self._store.sadd_with_expiry(_REGISTER_KEY_PREFIX + address, settings.freeze_register_ttl_seconds)

    async def is_in_register(self, address: str) -> bool:
        return await self._store.exists(_REGISTER_KEY_PREFIX + address)
