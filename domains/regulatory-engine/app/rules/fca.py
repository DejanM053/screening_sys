"""FCARule — UK (FCA/OFSI) (Section 9.2)."""
from __future__ import annotations

from typing import List

from app.models import RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import JurisdictionRule


class FCARule(JurisdictionRule):
    """UK. FCA SYSC 6.3 requires "appropriate" systems — no single threshold
    defined, so we apply the FATF baseline. PEP EDD is mandatory for all
    PEPs, domestic treated the same as foreign."""

    name = "FCARule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return "GB" in (payment.originator_country, payment.beneficiary_country)

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.UK_SANCTIONS_LIST, SanctionsList.OFSI_CONSOLIDATED]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        return [
            ReportingRequirement(
                regulator="OFSI",
                obligation="Report breach or suspected breach of financial sanctions",
                trigger="Knowledge or suspicion of a sanctions breach",
                deadline_days=3,
            )
        ]

    def get_retention_period_days(self) -> int:
        return 5 * 365
