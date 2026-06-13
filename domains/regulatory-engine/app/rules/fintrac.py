"""FINTRACRule — Canada (FINTRAC) (Section 9.2)."""
from __future__ import annotations

from typing import List

from app.models import RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import JurisdictionRule

LARGE_CASH_TRANSACTION_REPORT_CAD = 10_000


class FINTRACRule(JurisdictionRule):
    """Canada. OSFI Consolidated List + UN List. PCMLTFA mandates EDD for
    high-risk corridors. 5-year retention is the basis Sokin previously cited
    for refusing UK GDPR deletion requests (Section 2.2) — technically correct
    for Canadian customers."""

    name = "FINTRACRule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return "CA" in (payment.originator_country, payment.beneficiary_country)

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.OSFI_CONSOLIDATED, SanctionsList.UN_CONSOLIDATED]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        reqs = [
            ReportingRequirement(
                regulator="FINTRAC",
                obligation="Suspicious Transaction Report (STR)",
                trigger="Any REVIEW or MATCH verdict",
                deadline_days=None,
            )
        ]
        if payment.amount_usd >= LARGE_CASH_TRANSACTION_REPORT_CAD:
            reqs.append(
                ReportingRequirement(
                    regulator="FINTRAC",
                    obligation="Large Cash Transaction Report (LCTR)",
                    trigger=f"amount_usd >= {LARGE_CASH_TRANSACTION_REPORT_CAD} (CAD 10,000+)",
                    deadline_days=15,
                )
            )
        return reqs

    def get_retention_period_days(self) -> int:
        return 5 * 365

    def get_travel_rule_threshold_usd(self) -> float | None:
        return 1000.0
