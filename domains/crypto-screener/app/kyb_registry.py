"""KYB-verified wallet registry (Section 10.3 Step 1b)."""
from __future__ import annotations

from typing import Optional

from app.models import KYBRecord, UBOResolutionStatus
from app.store import KeyValueStore, dump, load

_REGISTRY_KEY_PREFIX = "kyb_wallet:"


class KYBWalletRegistry:
    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def register(self, address: str, record: KYBRecord) -> None:
        await self._store.set(_REGISTRY_KEY_PREFIX + address, dump(record.model_dump(mode="json")))

    async def lookup(self, address: str) -> Optional[KYBRecord]:
        raw = await self._store.get(_REGISTRY_KEY_PREFIX + address)
        if raw is None:
            return None
        return KYBRecord(**load(raw))

    async def is_internal_pair(self, address_a: str, address_b: str) -> bool:
        """Both addresses must be KYB-verified with FULL or PARTIAL UBO status.

        UNRESOLVED UBO status -> treated as external regardless of registry presence.
        """
        if not address_a or not address_b:
            return False

        record_a = await self.lookup(address_a)
        record_b = await self.lookup(address_b)
        if record_a is None or record_b is None:
            return False

        ok_statuses = (UBOResolutionStatus.FULL, UBOResolutionStatus.PARTIAL)
        return record_a.ubo_resolution_status in ok_statuses and record_b.ubo_resolution_status in ok_statuses
