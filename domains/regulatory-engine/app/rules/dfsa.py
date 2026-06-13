"""DFSARule — UAE (DFSA/CBUAE) (Section 9.2)."""
from __future__ import annotations

from typing import List

from app.models import RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import JurisdictionRule


class DFSARule(JurisdictionRule):
    """UAE. DFSA requires screening against all international lists plus the
    UAE local terrorist designation list. VARA requires VASP licensing and
    screening for crypto-asset activity."""

    name = "DFSARule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return "AE" in (payment.originator_country, payment.beneficiary_country)

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.UAE_LOCAL_TERRORIST_LIST, SanctionsList.OFAC_SDN, SanctionsList.UN_CONSOLIDATED]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        return [
            ReportingRequirement(
                regulator="DFSA / UAE FIU",
                obligation="Suspicious Transaction Report (STR)",
                trigger="Any REVIEW or MATCH verdict",
                deadline_days=None,
            )
        ]

    def get_retention_period_days(self) -> int:
        return 5 * 365

    def get_enhanced_due_diligence(self, payment: RegulatoryPaymentContext) -> bool:
        # VARA: crypto-asset activity requires VASP licensing and EDD.
        return payment.asset_type == "stablecoin"
