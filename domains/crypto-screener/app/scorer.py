"""Track B composite risk scorer — mirrors screening-api's six-factor weights (Section 6.3)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models import ScoreBreakdown, VerdictEnum, UBOResolutionStatus

W_IDENTITY = 0.25
W_BEHAVIORAL = 0.20
W_NETWORK = 0.20
W_ENTITY_PROFILE = 0.15
W_DOC_INTEGRITY = 0.10
W_HISTORICAL = 0.10

REVIEW_RISK_THRESHOLD = 0.50


@dataclass
class RawFactors:
    identity_match: float = 0.0
    behavioral_anomaly: float = 0.0
    network_exposure: float = 0.0
    entity_risk_profile: float = 0.0
    doc_integrity: float = 0.0
    historical_flag_rate: float = 0.0


def compute_composite(factors: RawFactors) -> ScoreBreakdown:
    composite = (
        W_IDENTITY * factors.identity_match
        + W_BEHAVIORAL * factors.behavioral_anomaly
        + W_NETWORK * factors.network_exposure
        + W_ENTITY_PROFILE * factors.entity_risk_profile
        + W_DOC_INTEGRITY * factors.doc_integrity
        + W_HISTORICAL * factors.historical_flag_rate
    )
    composite = max(0.0, min(1.0, composite))

    return ScoreBreakdown(
        identity_match=factors.identity_match,
        behavioral_anomaly=factors.behavioral_anomaly,
        network_exposure=factors.network_exposure,
        entity_risk_profile=factors.entity_risk_profile,
        doc_integrity=factors.doc_integrity,
        historical_flag_rate=factors.historical_flag_rate,
        composite=composite,
    )


def recommend_verdict(
    ofac_match: bool,
    issuer_frozen: bool,
    country_block: bool,
    composite: float,
    ubo_status: UBOResolutionStatus,
) -> VerdictEnum:
    """Mirrors the two-track invariant: only deterministic gates produce MATCH."""
    if ofac_match or issuer_frozen or country_block:
        return VerdictEnum.MATCH

    if ubo_status == UBOResolutionStatus.UNRESOLVED:
        return VerdictEnum.REVIEW

    if composite >= REVIEW_RISK_THRESHOLD:
        return VerdictEnum.REVIEW

    return VerdictEnum.NO_MATCH
