"""Free wallet attribution via Etherscan/Tronscan address labels (CC-05 #5).

Only called for non-KYB-verified (external) addresses.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.models import WalletAttribution

logger = logging.getLogger("crypto-screener.attribution")

MIXER_SCORE_BOOST = 0.40

_MIXER_LABELS = {
    "tornado cash",
    "tornado cash router",
    "chipmixer",
    "sinbad",
    "blender.io",
}

_CATEGORY_BY_LABEL_KEYWORD = {
    "exchange": "exchange",
    "mixer": "mixer",
    "darknet": "darknet",
    "defi": "defi_protocol",
    "sanctioned": "sanctioned",
}


class WalletAttributor:
    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client

    async def lookup(self, address: str, chain: str) -> Optional[WalletAttribution]:
        try:
            label = await self._fetch_label(address, chain)
        except Exception as exc:  # pragma: no cover - exercised only without network access
            logger.warning("Attribution lookup unavailable for %s on %s: %s", address, chain, exc)
            return WalletAttribution(label=None, category="unknown")

        if label is None:
            return WalletAttribution(label=None, category="unknown")

        normalized = label.lower()
        category = "unknown"
        if normalized in _MIXER_LABELS:
            category = "mixer"
        else:
            for keyword, mapped in _CATEGORY_BY_LABEL_KEYWORD.items():
                if keyword in normalized:
                    category = mapped
                    break

        return WalletAttribution(label=label, category=category)

    async def _fetch_label(self, address: str, chain: str) -> Optional[str]:
        chain = chain.lower()
        client = self._client or httpx.AsyncClient(timeout=5.0)
        owns_client = self._client is None
        try:
            if chain == "tron":
                resp = await client.get(f"{settings.tronscan_api_url}/api/account", params={"address": address})
            else:
                resp = await client.get(
                    f"{settings.etherscan_api_url}/api",
                    params={"module": "contract", "action": "getsourcecode", "address": address},
                )
            resp.raise_for_status()
            data = resp.json()
            return data.get("label") or data.get("name")
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def is_mixer(attribution: Optional[WalletAttribution]) -> bool:
        return attribution is not None and attribution.category == "mixer"
