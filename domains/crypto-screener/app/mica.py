"""MiCA compliance tagging + TRON EU/UK corridor policy flag (Sections 9.2, 10.3).

These are informational policy flags only — they never modify the numeric
risk score. Primary source of truth is the regulatory-engine
(`tron_corridor_policy.py`, `eu_aml.py`); this module provides a local,
dependency-free fallback so crypto-screener can still tag transactions if
the regulatory-engine is unreachable. The regulatory-engine is also the
authoritative source for `country_block` (FATF BLACK-tier corridors) — the
local fallback cannot determine this without the FATF tier config.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("crypto-screener.mica")

EU_EEA_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE", "IS", "LI", "NO",
}
EU_AND_UK = EU_EEA_COUNTRIES | {"GB"}


@dataclass
class CountryPolicyResult:
    mica_compliance_risk: bool = False
    tron_eu_corridor_review: bool = False
    country_block: bool = False
    country_sanctions_program: Optional[str] = None


class MiCAComplianceTagger:
    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client

    async def check(
        self, token: str, chain: str, originator_country: str, beneficiary_country: str
    ) -> CountryPolicyResult:
        try:
            return await self._check_via_regulatory_engine(token, chain, originator_country, beneficiary_country)
        except Exception as exc:  # pragma: no cover - exercised only without network access
            logger.warning("Regulatory-engine unreachable; using local MiCA/TRON fallback: %s", exc)
            return self._check_local(token, chain, originator_country, beneficiary_country)

    async def _check_via_regulatory_engine(
        self, token: str, chain: str, originator_country: str, beneficiary_country: str
    ) -> CountryPolicyResult:
        client = self._client or httpx.AsyncClient(timeout=5.0)
        owns_client = self._client is None
        try:
            resp = await client.post(
                f"{settings.regulatory_engine_url}/get-requirements",
                json={
                    "originator_country": originator_country,
                    "beneficiary_country": beneficiary_country,
                    "amount_usd": 0.0,
                    "entity_type": "business",
                    "asset_type": "stablecoin",
                    "chain": chain,
                    "token": token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return CountryPolicyResult(
                mica_compliance_risk=bool(data.get("mica_compliance_risk", False)),
                tron_eu_corridor_review=bool(data.get("tron_eu_corridor_review", False)),
                country_block=bool(data.get("auto_block", False)),
                country_sanctions_program=data.get("country_sanctions_program"),
            )
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _check_local(token: str, chain: str, originator_country: str, beneficiary_country: str) -> CountryPolicyResult:
        token = token.upper()
        chain = chain.lower()
        corridor_countries = {originator_country, beneficiary_country}

        mica_flag = token == "USDT" and bool(corridor_countries & EU_EEA_COUNTRIES)
        tron_eu_flag = chain == "tron" and token == "USDT" and bool(corridor_countries & EU_AND_UK)
        return CountryPolicyResult(mica_compliance_risk=mica_flag, tron_eu_corridor_review=tron_eu_flag)
