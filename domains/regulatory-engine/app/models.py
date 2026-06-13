"""Pydantic models for the regulatory-engine service (CC-04)."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SanctionsList(str, Enum):
    OFAC_SDN = "OFAC_SDN"
    OFAC_CONSOLIDATED = "OFAC_CONSOLIDATED"
    BIS_ENTITY_LIST = "BIS_ENTITY_LIST"
    UK_SANCTIONS_LIST = "UK_SANCTIONS_LIST"
    OFSI_CONSOLIDATED = "OFSI_CONSOLIDATED"
    EU_CONSOLIDATED = "EU_CONSOLIDATED"
    EU_TERRORISM = "EU_TERRORISM"
    UN_CONSOLIDATED = "UN_CONSOLIDATED"
    DFAT_CONSOLIDATED = "DFAT_CONSOLIDATED"
    OSFI_CONSOLIDATED = "OSFI_CONSOLIDATED"
    UAE_LOCAL_TERRORIST_LIST = "UAE_LOCAL_TERRORIST_LIST"
    PEP = "PEP"


class PolicyFlag(str, Enum):
    MICA_COMPLIANCE_RISK = "MICA_COMPLIANCE_RISK"
    TRON_EU_CORRIDOR_REVIEW = "TRON_EU_CORRIDOR_REVIEW"


class CountryRiskTier(str, Enum):
    BLACK = "BLACK"
    GREY = "GREY"
    HIGH_RISK = "HIGH_RISK"
    OFFSHORE = "OFFSHORE"
    STANDARD = "STANDARD"


class RegulatoryPaymentContext(BaseModel):
    """Input to POST /get-requirements. Mirrors the relevant subset of
    screening-api's Payment model — kept separate so this service has no
    hard dependency on screening-api's schema."""

    originator_country: str
    beneficiary_country: str
    amount_usd: float
    entity_type: str = "business"
    asset_type: str = "fiat"  # fiat | stablecoin
    chain: Optional[str] = None  # tron | ethereum | solana | base | arbitrum
    token: Optional[str] = None  # USDT | USDC | PYUSD | EURC


class ScoreThresholds(BaseModel):
    match: float = Field(0.85, ge=0.0, le=1.0)
    review: float = Field(0.50, ge=0.0, le=1.0)


class ReportingRequirement(BaseModel):
    regulator: str
    obligation: str
    trigger: str
    deadline_days: Optional[int] = None


class ScreeningRequirements(BaseModel):
    required_lists: List[SanctionsList]
    enhanced_due_diligence: bool = False
    travel_rule_threshold_usd: Optional[float] = None
    notes: List[str] = Field(default_factory=list)


class CountryRiskResult(BaseModel):
    country: str
    tier: CountryRiskTier
    score_multiplier: float
    auto_block: bool
    description: str


class GetRequirementsResponse(BaseModel):
    # CC-04 structured fields
    required_lists: List[SanctionsList]
    thresholds: ScoreThresholds
    reporting_obligations: List[ReportingRequirement]
    country_risk_tiers: dict[str, CountryRiskResult]
    applicable_rules: List[str]
    travel_rule_required: bool
    policy_flags: List[PolicyFlag]

    # Flattened convenience fields consumed directly by screening-api
    auto_block: bool = False
    country_sanctions_program: Optional[str] = None
    review_threshold: float = 0.50
    country_risk_multiplier: float = 1.0
    mica_compliance_risk: bool = False
    tron_eu_corridor_review: bool = False
    retention_period_days: int = 1825
