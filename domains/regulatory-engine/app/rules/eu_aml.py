"""EUAMLRule — EU/EEA (EBA/AMLA/MiCA) (Section 9.2)."""
from __future__ import annotations

from typing import List

from app.models import PolicyFlag, RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import EU_EEA_COUNTRIES, JurisdictionRule


class EUAMLRule(JurisdictionRule):
    """EU/EEA. EU Consolidated + EU Terrorism + UN lists. MiCA Article 48:
    USDT is not MiCA-authorized as of mid-2026, so any USDT transfer on an
    EU corridor carries MICA_COMPLIANCE_RISK (informational, not a score
    modifier). USDC (MiCA-authorized) does not."""

    name = "EUAMLRule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return (
            payment.originator_country.upper() in EU_EEA_COUNTRIES
            or payment.beneficiary_country.upper() in EU_EEA_COUNTRIES
        )

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.EU_CONSOLIDATED, SanctionsList.EU_TERRORISM, SanctionsList.UN_CONSOLIDATED]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        return [
            ReportingRequirement(
                regulator="AMLA / national FIU",
                obligation="EU Transfer of Funds Regulation (TFR) originator/beneficiary data",
                trigger="Any crypto-asset transfer (EUR 0 threshold)",
                deadline_days=None,
            )
        ]

    def get_retention_period_days(self) -> int:
        return 5 * 365

    def get_travel_rule_threshold_usd(self) -> float | None:
        return 0.0

    def get_policy_flags(self, payment: RegulatoryPaymentContext) -> List[PolicyFlag]:
        if payment.asset_type == "stablecoin" and (payment.token or "").upper() == "USDT":
            return [PolicyFlag.MICA_COMPLIANCE_RISK]
        return []
