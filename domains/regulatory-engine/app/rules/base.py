"""JurisdictionRule abstract base class (CC-04)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.models import (
    PolicyFlag,
    RegulatoryPaymentContext,
    ReportingRequirement,
    SanctionsList,
    ScoreThresholds,
)

# EU/EEA member country codes (ISO 3166-1 alpha-2). Used by EUAMLRule and
# TRONCorriderPolicyRule to determine "EU corridor" payments.
EU_EEA_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO",
    "PL", "PT", "RO", "SE", "SI", "SK",
}


class JurisdictionRule(ABC):
    """Pluggable per-jurisdiction rule (Section 9.1)."""

    name: str

    @abstractmethod
    def applies_to(self, payment: RegulatoryPaymentContext) -> bool:
        """Does this rule apply to this payment corridor?"""

    @abstractmethod
    def get_required_lists(self) -> List[SanctionsList]:
        """Which lists must be checked."""

    @abstractmethod
    def get_thresholds(self) -> ScoreThresholds:
        """MATCH/REVIEW thresholds for this jurisdiction."""

    @abstractmethod
    def get_reporting_requirements(self, payment: RegulatoryPaymentContext) -> List[ReportingRequirement]:
        """Reporting obligations triggered by this payment."""

    @abstractmethod
    def get_retention_period_days(self) -> int:
        """How long audit records must be kept."""

    def get_policy_flags(self, payment: RegulatoryPaymentContext) -> List[PolicyFlag]:
        """Informational policy flags (default: none)."""
        return []

    def get_travel_rule_threshold_usd(self) -> float | None:
        """Travel Rule reporting threshold in USD (None if not applicable)."""
        return None

    def get_enhanced_due_diligence(self, payment: RegulatoryPaymentContext) -> bool:
        return False
