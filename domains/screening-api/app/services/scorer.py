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
