"""Jurisdiction-specific audit retention periods (Section 9.2 / CC-audit-trail).

Mirrors the retention periods returned by regulatory-engine's JurisdictionRule
implementations. audit-trail keeps its own copy so it has no runtime
dependency on regulatory-engine — retention is computed at write time from
the countries on the payment.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

DAYS_5_YEARS = 5 * 365
DAYS_7_YEARS = 7 * 365

# Country code -> retention days. Countries not listed fall back to DEFAULT_RETENTION_DAYS.
RETENTION_DAYS_BY_COUNTRY: dict[str, int] = {
    "US": DAYS_5_YEARS,   # FinCEN
    "GB": DAYS_5_YEARS,   # FCA / OFSI (MLRO records)
    "CA": DAYS_5_YEARS,   # FINTRAC
    "AU": DAYS_7_YEARS,   # AML/CTF Act 2006
    "AE": DAYS_5_YEARS,   # DFSA
}

# EU/EEA: 5 years standard, 10 years for high-risk corridors (Section 9.2).
EU_EEA_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO",
    "PL", "PT", "RO", "SE", "SI", "SK",
}
EU_HIGH_RISK_RETENTION_DAYS = 10 * 365
EU_STANDARD_RETENTION_DAYS = DAYS_5_YEARS

DEFAULT_RETENTION_DAYS = DAYS_5_YEARS


def retention_days_for(country_codes: Iterable[Optional[str]], high_risk: bool = False) -> int:
    """Longest applicable retention period across the given countries."""
    days = DEFAULT_RETENTION_DAYS
    for code in country_codes:
        if not code:
            continue
        code = code.upper()
        if code in EU_EEA_COUNTRIES:
            eu_days = EU_HIGH_RISK_RETENTION_DAYS if high_risk else EU_STANDARD_RETENTION_DAYS
            days = max(days, eu_days)
        days = max(days, RETENTION_DAYS_BY_COUNTRY.get(code, DEFAULT_RETENTION_DAYS))
    return days


def compute_retention_until(
    screened_at: datetime,
    country_codes: Iterable[Optional[str]],
    high_risk: bool = False,
) -> datetime:
    return screened_at + timedelta(days=retention_days_for(country_codes, high_risk=high_risk))
