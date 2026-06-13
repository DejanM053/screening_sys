"""OFACRule — US / FinCEN (Section 9.2)."""
from __future__ import annotations

from typing import List

from app.models import RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import JurisdictionRule


class OFACRule(JurisdictionRule):
    """US (OFAC/FinCEN). Near-zero tolerance — even 50% ownership by an SDN
    entity is a Track A block (enforced in screening-api's verdicts.py),
    so the Track B thresholds here are deliberately tighter than the FATF
    baseline."""

    name = "OFACRule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return "US" in (payment.originator_country, payment.beneficiary_country)

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.OFAC_SDN, SanctionsList.OFAC_CONSOLIDATED, SanctionsList.BIS_ENTITY_LIST]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.30)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        return [
            ReportingRequirement(
                regulator="FinCEN",
                obligation="Suspicious Activity Report (SAR)",
                trigger="Any verdict requiring escalation (REVIEW or MATCH)",
                deadline_days=30,
            )
        ]

    def get_retention_period_days(self) -> int:
        return 5 * 365

    def get_travel_rule_threshold_usd(self) -> float | None:
        return 3000.0
