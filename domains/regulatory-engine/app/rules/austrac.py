"""AUSTRACRule — Australia (AUSTRAC/ASIC) (Section 9.2)."""
from __future__ import annotations

from typing import List

from app.models import RegulatoryPaymentContext, ReportingRequirement, SanctionsList, ScoreThresholds
from app.rules.base import JurisdictionRule

# AML/CTF Act 2006 threshold transaction reporting (AUD 10,000). We treat the
# configured amount_usd against this AUD-denominated threshold directly, as
# country_risk_tiers.yaml and screening-api operate in USD-equivalent terms.
THRESHOLD_TRANSACTION_REPORT_AUD = 10_000


class AUSTRACRule(JurisdictionRule):
    """Australia. DFAT Consolidated List; no de minimis exemption for
    sanctions screening regardless of amount."""

    name = "AUSTRACRule"

    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        return "AU" in (payment.originator_country, payment.beneficiary_country)

    def get_required_lists(self) -> List[SanctionsList]:
        return [SanctionsList.DFAT_CONSOLIDATED]

    def get_thresholds(self) -> ScoreThresholds:
        return ScoreThresholds(match=0.85, review=0.50)

    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        reqs = [
            ReportingRequirement(
                regulator="AUSTRAC",
                obligation="Suspicious Matter Report (SMR)",
                trigger="Any REVIEW or MATCH verdict — real-time reporting",
                deadline_days=None,
            )
        ]
        if payment.amount_usd >= THRESHOLD_TRANSACTION_REPORT_AUD:
            reqs.append(
                ReportingRequirement(
                    regulator="AUSTRAC",
                    obligation="Threshold Transaction Report (TTR)",
                    trigger=f"amount_usd >= {THRESHOLD_TRANSACTION_REPORT_AUD} (AUD 10,000+)",
                    deadline_days=10,
                )
            )
        return reqs

    def get_retention_period_days(self) -> int:
        return 7 * 365

    def get_travel_rule_threshold_usd(self) -> float | None:
        return 1000.0
