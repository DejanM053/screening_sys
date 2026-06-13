"""TRONCorriderPolicyRule — TRON/USDT EU+UK corridor policy flag (Section 9.2).

Not a jurisdiction rule in the legal sense — a business-policy rule. While
Tether's MiCA authorization is unresolved, TRON-settled USDT transfers on EU
or UK corridors carry an informational TRON_EU_CORRIDOR_REVIEW tag for
analyst attention. Does NOT modify the numeric score or required lists.
"""
from __future__ import annotations

from typing import List

from app.models import PolicyFlag, RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import EU_EEA_COUNTRIES, JurisdictionRule

EU_AND_UK = EU_EEA_COUNTRIES | {"GB"}


class TRONCorriderPolicyRule(JurisdictionRule):
    name = "TRONCorriderPolicyRule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        if (payment.chain or "").lower() != "tron":
            return False
        return (
            payment.originator_country.upper() in EU_AND_UK
            or payment.beneficiary_country.upper() in EU_AND_UK
        )

    def get_required_lists(self) -> List[SanctionsList]:
        return []

    def get_thresholds(self) -> ScoreThresholds:
        # Neutral — this rule never tightens MATCH/REVIEW thresholds.
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        return []

    def get_retention_period_days(self) -> int:
        return 5 * 365

    def get_policy_flags(self, payment: RegulatoryPaymentContext) -> List[PolicyFlag]:
        return [PolicyFlag.TRON_EU_CORRIDOR_REVIEW]
