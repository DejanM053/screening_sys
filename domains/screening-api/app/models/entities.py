from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    BUSINESS = "business"
    INDIVIDUAL = "individual"  # future KYC extension


class UBOResolutionStatus(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"


class VerdictEnum(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"


class TrackLabel(str, Enum):
    A_IDENTITY = "A:identity"
    A_FIFTY_PCT_RULE = "A:50pct-rule"
    A_COUNTRY_SANCTIONS = "A:country-sanctions"
    A_PARTIAL = "A:partial"
    B_RISK = "B:risk"


class Payment(BaseModel):
    payment_id: str
    originator_name: str
    originator_country: str
    originator_wallet: Optional[str] = None
    originator_registration_number: Optional[str] = None
    beneficiary_name: str
    beneficiary_country: str
    beneficiary_wallet: Optional[str] = None
    beneficiary_registration_number: Optional[str] = None
    amount_usd: float
    asset_type: str = "fiat"  # fiat | USDT | USDC
    chain: Optional[str] = None  # tron | ethereum | solana
    entity_type: EntityType = EntityType.BUSINESS
    # nullable KYC fields (future extension)
    dob: Optional[str] = None
    passport_number: Optional[str] = None
    biometric_reference: Optional[str] = None


class ScreeningRequest(BaseModel):
    payment: Payment
    analyst_id: Optional[str] = None
    bypass_cache: bool = False


class ScoreBreakdown(BaseModel):
    identity_match: float = Field(0.0, ge=0.0, le=1.0)
    behavioral_anomaly: float = Field(0.0, ge=0.0, le=1.0)
    network_exposure: float = Field(0.0, ge=0.0, le=1.0)
    entity_risk_profile: float = Field(0.0, ge=0.0, le=1.0)
    doc_integrity: float = Field(0.0, ge=0.0, le=1.0)
    historical_flag_rate: float = Field(0.0, ge=0.0, le=1.0)
    ml_delta: float = Field(0.0, ge=0.0, le=0.15)
    composite: float = Field(0.0, ge=0.0, le=1.0)


class PolicyFlags(BaseModel):
    mica_compliance_risk: bool = False
    tron_eu_corridor_review: bool = False
    pep_flag: bool = False


class Verdict(BaseModel):
    verdict: VerdictEnum
    track: TrackLabel
    cause: str
    composite_score: float = Field(0.0, ge=0.0, le=1.0)
    priority: float = Field(0.0, ge=0.0, le=1.0)
    ubo_resolution_status: UBOResolutionStatus = UBOResolutionStatus.FULL
    policy_flags: PolicyFlags = Field(default_factory=PolicyFlags)
    score_breakdown: Optional[ScoreBreakdown] = None
    explanation_tree: Optional[Dict[str, Any]] = None
    list_version_ofac: Optional[str] = None
    list_version_ofsi: Optional[str] = None
    algorithm_version: str = "v1.2"
    screened_at: datetime = Field(default_factory=datetime.utcnow)


class ScreeningResult(BaseModel):
    payment_id: str
    verdict: Verdict
    processing_time_ms: float
    cached: bool = False


class WalletScreenResult(BaseModel):
    address: str
    chain: str
    kyb_verified: bool = False
    is_internal: bool = False
    ofac_match: bool = False
    issuer_frozen: bool = False
    hop_score: float = Field(0.0, ge=0.0, le=1.0)
    attribution: Optional[str] = None  # exchange | mixer | darknet | unknown
    mica_flag: bool = False
    composite_score: float = Field(0.0, ge=0.0, le=1.0)
    recommended_verdict: VerdictEnum = VerdictEnum.NO_MATCH


class SanctionsGateResult(BaseModel):
    """Track A deterministic result."""
    identity_confirmed: bool = False
    identity_partial: bool = False
    owned_50pct_by_named_sdn: bool = False
    comprehensive_sanctions_jurisdiction: bool = False
    name_composite: float = 0.0
    list_evidence: Optional[str] = None
    ownership_path: Optional[str] = None
    country_sanctions_program: Optional[str] = None
