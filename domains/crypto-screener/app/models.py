from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class UBOResolutionStatus(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"


class VerdictEnum(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"


class KYBRecord(BaseModel):
    entity_id: str
    ubo_resolution_status: UBOResolutionStatus
    onboarding_score: float = Field(0.0, ge=0.0, le=1.0)
    kyb_verified_at: datetime
    historical_flag_rate: float = Field(0.0, ge=0.0, le=1.0)


class HopAnalysis(BaseModel):
    hop_score: float = Field(0.0, ge=0.0, le=1.0)
    hops_traced: int = 0
    total_value_traced_usd: float = 0.0
    path: List[str] = Field(default_factory=list)
    truncated_de_minimis: bool = False


class IssuerBlacklistResult(BaseModel):
    frozen: bool = False
    chain: str
    issuer: Optional[str] = None


class WalletAttribution(BaseModel):
    label: Optional[str] = None
    category: Optional[str] = None  # exchange | mixer | darknet | defi_protocol | sanctioned | unknown


class TravelRuleStatus(BaseModel):
    required: bool = False
    threshold_usd: float = 0.0
    compliant: bool = True
    action: Optional[str] = None
    reason: Optional[str] = None


class StablecoinTransaction(BaseModel):
    chain: str  # tron | ethereum | solana | base | arbitrum
    stablecoin: str  # USDT | USDC | PYUSD | EURC
    from_address: str
    to_address: str
    amount_usd: float
    originator_vasp: Optional[str] = None
    beneficiary_vasp: Optional[str] = None
    is_internal: bool = False


class ScreenWalletRequest(BaseModel):
    address: str
    chain: str
    stablecoin: str = "USDT"
    amount_usd: float = 0.0
    counterparty_address: str = ""
    corridor: str = ""
    originator_country: Optional[str] = None
    beneficiary_country: Optional[str] = None


class ScoreBreakdown(BaseModel):
    identity_match: float = Field(0.0, ge=0.0, le=1.0)
    behavioral_anomaly: float = Field(0.0, ge=0.0, le=1.0)
    network_exposure: float = Field(0.0, ge=0.0, le=1.0)
    entity_risk_profile: float = Field(0.0, ge=0.0, le=1.0)
    doc_integrity: float = Field(0.0, ge=0.0, le=1.0)
    historical_flag_rate: float = Field(0.0, ge=0.0, le=1.0)
    composite: float = Field(0.0, ge=0.0, le=1.0)


class ScreenWalletResponse(BaseModel):
    address: str
    chain: str

    kyb_verified: bool = False
    is_internal: bool = False
    entity_id: Optional[str] = None
    ubo_status: UBOResolutionStatus = UBOResolutionStatus.UNRESOLVED

    ofac_match: bool = False
    ofac_score: float = Field(0.0, ge=0.0, le=1.0)

    country_block: bool = False
    country_sanctions_program: Optional[str] = None

    issuer_frozen: bool = False
    issuer: Optional[str] = None

    hop_analysis: HopAnalysis = Field(default_factory=HopAnalysis)
    hop_score: float = Field(0.0, ge=0.0, le=1.0)

    attribution: Optional[str] = None
    volume_anomaly_score: float = Field(0.0, ge=0.0, le=1.0)

    mica_flag: bool = False
    tron_eu_corridor_flag: bool = False

    travel_rule: TravelRuleStatus = Field(default_factory=TravelRuleStatus)

    entity_risk_score: float = Field(0.0, ge=0.0, le=1.0)
    historical_flag_rate: float = Field(0.0, ge=0.0, le=1.0)

    composite_score: float = Field(0.0, ge=0.0, le=1.0)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    recommended_verdict: VerdictEnum = VerdictEnum.NO_MATCH
