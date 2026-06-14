"""On-chain hop tracing via Tronscan (primary) / Etherscan (secondary).

Linear -0.3/hop decay (Section 10.3), intentionally distinct from the
geometric 0.5^d noisy-OR decay used for ownership/shared-attribute graphs
(Section 6.4) — on-chain hops are confirmed fund-flow edges, not
probabilistic contamination.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.models import HopAnalysis
from app.store import KeyValueStore, dump, load

logger = logging.getLogger("crypto-screener.hop_tracer")

_DE_MINIMIS_USD = 1000.0
_HOP_SCORES = {0: 1.0, 1: 0.7, 2: 0.4, 3: 0.1}
_CACHE_PREFIX = "hop_trace:"


class OnChainHopTracer:
    def __init__(self, store: KeyValueStore, client: Optional[httpx.AsyncClient] = None) -> None:
        self._store = store
        self._client = client

    async def trace(self, address: str, chain: str, max_hops: int) -> HopAnalysis:
        cache_key = f"{_CACHE_PREFIX}{chain}:{address}:{max_hops}"
        cached = await self._store.get(cache_key)
        if cached is not None:
            return HopAnalysis(**load(cached))

        result = await self._trace_uncached(address, chain, max_hops)
        await self._store.set(cache_key, dump(result.model_dump(mode="json")), ttl_seconds=settings.hop_cache_ttl_seconds)
        return result

    async def _trace_uncached(self, address: str, chain: str, max_hops: int) -> HopAnalysis:
        try:
            counterparties = await self._fetch_counterparties(address, chain)
        except Exception as exc:  # pragma: no cover - exercised only without network access
            logger.warning("Hop trace unavailable for %s on %s: %s", address, chain, exc)
            return HopAnalysis(hop_score=0.0, hops_traced=0, total_value_traced_usd=0.0, path=[])

        path: list[str] = []
        total_value = 0.0
        hop_score = 0.0
        for hop_index, counterparty in enumerate(counterparties[:max_hops], start=1):
            value_usd = counterparty.get("value_usd", 0.0)
            total_value += value_usd
            path.append(counterparty.get("address", ""))
            hop_score = max(hop_score, _HOP_SCORES.get(hop_index, 0.0))
            if total_value < _DE_MINIMIS_USD:
                continue
            if counterparty.get("flagged"):
                break

        return HopAnalysis(
            hop_score=hop_score,
            hops_traced=len(path),
            total_value_traced_usd=total_value,
            path=path,
            truncated_de_minimis=total_value < _DE_MINIMIS_USD,
        )

    async def _fetch_counterparties(self, address: str, chain: str) -> list[dict]:
        chain = chain.lower()
        client = self._client or httpx.AsyncClient(timeout=5.0)
        owns_client = self._client is None
        try:
            if chain == "tron":
                resp = await client.get(
                    f"{settings.tronscan_api_url}/api/token_trc20/transfers",
                    params={"address": address, "limit": 20, "start": 0},
                )
            else:
                resp = await client.get(
                    f"{settings.etherscan_api_url}/api",
                    params={
                        "module": "account",
                        "action": "tokentx",
                        "address": address,
                        "apikey": settings.etherscan_api_key,
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            return data.get("counterparties", data.get("result", []) if isinstance(data.get("result"), list) else [])
        finally:
            if owns_client:
                await client.aclose()
