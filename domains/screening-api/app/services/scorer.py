"""Track B composite risk scorer — Section 6.3 six-factor weighted sum."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.entities import ScoreBreakdown

# Factor weights — sum = 1.0 (Section 6.3)
W_IDENTITY = 0.25
W_BEHAVIORAL = 0.20
W_NETWORK = 0.20
W_ENTITY_PROFILE = 0.15
W_DOC_INTEGRITY = 0.10
W_HISTORICAL = 0.10
ML_CAP = 0.15


@dataclass
class RawFactors:
    identity_match: float = 0.0        # from entity-resolution domain
    behavioral_anomaly: float = 0.0    # from transaction history
    network_exposure: float = 0.0      # from graph-engine domain (noisy-OR)
    entity_risk_profile: float = 0.0   # from entity metadata + UBO flags
    doc_integrity: float = 0.0         # from onboarding documents
    historical_flag_rate: float = 0.0  # beta-binomial smoothed rate
    ml_delta: float = 0.0              # LightGBM bounded delta (max 0.15)


def compute_composite(factors: RawFactors) -> ScoreBreakdown:
    """
    Compute Track B composite risk score R ∈ [0, 1].

    R = clamp01( sum(w_i * factor_i) )
    R = clamp01( R + min(ml_delta, ML_CAP) )

    The ML delta is a supplementary opinion — bounded, never dominates.
    """
    base = (
        W_IDENTITY * factors.identity_match
        + W_BEHAVIORAL * factors.behavioral_anomaly
        + W_NETWORK * factors.network_exposure
        + W_ENTITY_PROFILE * factors.entity_risk_profile
        + W_DOC_INTEGRITY * factors.doc_integrity
        + W_HISTORICAL * factors.historical_flag_rate
    )
    base = _clamp01(base)

    bounded_ml = min(abs(factors.ml_delta), ML_CAP)
    composite = _clamp01(base + bounded_ml)

    return ScoreBreakdown(
        identity_match=factors.identity_match,
        behavioral_anomaly=factors.behavioral_anomaly,
        network_exposure=factors.network_exposure,
        entity_risk_profile=factors.entity_risk_profile,
        doc_integrity=factors.doc_integrity,
        historical_flag_rate=factors.historical_flag_rate,
        ml_delta=bounded_ml,
        composite=composite,
    )


def entity_risk_from_metadata(
    amount_usd: float,
    originator_country: str,
    beneficiary_country: str,
    entity_type: str,
    country_risk_multiplier: float = 1.0,
    ubo_resolution_status: str = "FULL",
) -> float:
    """Deterministic entity risk score from payment metadata (Factor 4, 15%).

    Produces a non-zero baseline so the demo shows meaningful scores even
    when entity-resolution has no list matches.
    """
    score = 0.0

    # High-value payment risk
    if amount_usd >= 1_000_000:
        score += 0.3
    elif amount_usd >= 100_000:
        score += 0.15
    elif amount_usd >= 10_000:
        score += 0.05

    # UBO resolution status
    if ubo_resolution_status == "UNRESOLVED":
        score += 0.4
    elif ubo_resolution_status == "PARTIAL":
        score += 0.2

    # Cross-border uplift for high-risk corridors (not BLACK tier, but elevated)
    _elevated = {"IR", "KP", "SY", "MM", "CU", "BY", "SD", "RU"}
    if originator_country in _elevated or beneficiary_country in _elevated:
        score += 0.5  # handled by auto_block; add less here to avoid double-count
    elif originator_country != beneficiary_country:
        score += 0.05

    # Apply country risk multiplier from regulatory engine
    score = min(1.0, score * max(country_risk_multiplier, 1.0))

    # Base noise floor so the factor always contributes a little
    score = max(score, 0.05)

    return _clamp01(score)


def beta_binomial_smoothed_rate(
    n_screen: int,
    k_true: int,
    alpha: float = 1.0,
    beta: float = 9.0,
) -> float:
    """
    Beta-Binomial smoothed prior flag rate (Section 6.5).

    smoothed = (k_true + alpha) / (n_screen + alpha + beta)

    Prior alpha=1, beta=9 → 10% baseline; small counts pull toward baseline.
    """
    return (k_true + alpha) / (n_screen + alpha + beta)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))
