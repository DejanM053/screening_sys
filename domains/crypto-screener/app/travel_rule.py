"""FATF Travel Rule enforcement (Section 10.5)."""
from __future__ import annotations

from typing import Optional

from app.mica import EU_EEA_COUNTRIES
from app.models import TravelRuleStatus

THRESHOLD_US_USD = 3000.0
THRESHOLD_EU_USD = 0.0
THRESHOLD_UK_USD = 0.0
THRESHOLD_AU_USD = 1000.0
THRESHOLD_CA_USD = 1000.0
THRESHOLD_DEFAULT_USD = 1000.0  # FATF Recommendation 16, as locally transposed


class TravelRuleEnforcer:
    @staticmethod
    def get_threshold(originator_country: str) -> float:
        country = originator_country.upper()
        if country == "US":
            return THRESHOLD_US_USD
        if country in EU_EEA_COUNTRIES:
            return THRESHOLD_EU_USD
        if country == "GB":
            return THRESHOLD_UK_USD
        if country == "AU":
            return THRESHOLD_AU_USD
        if country == "CA":
            return THRESHOLD_CA_USD
        return THRESHOLD_DEFAULT_USD

    def enforce(
        self,
        amount_usd: float,
        originator_country: str,
        is_internal: bool,
        beneficiary_vasp_travel_rule_enabled: Optional[bool] = None,
    ) -> TravelRuleStatus:
        threshold = self.get_threshold(originator_country)
        if amount_usd < threshold:
            return TravelRuleStatus(required=False, threshold_usd=threshold, compliant=True)

        if is_internal:
            # KYB platform members: Travel Rule packet auto-generated from the
            # KYB record (legal name, registered address, registration number).
            return TravelRuleStatus(
                required=True,
                threshold_usd=threshold,
                compliant=True,
                reason="Travel Rule data packet generated from KYB record",
            )

        if beneficiary_vasp_travel_rule_enabled is False:
            return TravelRuleStatus(
                required=True,
                threshold_usd=threshold,
                compliant=False,
                action="BLOCK_OR_REVIEW",
                reason="Beneficiary VASP does not support Travel Rule data exchange",
            )

        if beneficiary_vasp_travel_rule_enabled is None:
            return TravelRuleStatus(
                required=True,
                threshold_usd=threshold,
                compliant=False,
                action="REVIEW",
                reason="External counterparty — Travel Rule data not yet collected",
            )

        return TravelRuleStatus(required=True, threshold_usd=threshold, compliant=True)
