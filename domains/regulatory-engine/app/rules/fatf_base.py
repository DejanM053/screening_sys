"""FATFBaseRule — fallback applied when no specific jurisdiction rule matches."""
from __future__ import annotations

from typing import List

from app.models import RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import JurisdictionRule


class FATFBaseRule(JurisdictionRule):
    """FATF baseline. Applied when no specific jurisdiction rule matches the
    payment's corridor — every payment is screened against the UN and OFAC
    SDN lists at minimum, with FATF Recommendation 16 Travel Rule defaults."""

    name = "FATFBaseRule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return True

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.UN_CONSOLIDATED, SanctionsList.OFAC_SDN]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        return [
            ReportingRequirement(
                regulator="Local FIU",
                obligation="Suspicious Transaction Report (per FATF Recommendation 16)",
                trigger="Any REVIEW or MATCH verdict",
                deadline_days=None,
            )
        ]

    def get_retention_period_days(self) -> int:
        return 5 * 365

    def get_travel_rule_threshold_usd(self) -> float | None:
        return 1000.0
