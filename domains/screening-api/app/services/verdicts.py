"""Verdict resolution logic — two-track architecture (Section 6.2)."""
from __future__ import annotations

from app.models.entities import (
    PolicyFlags,
    SanctionsGateResult,
    ScoreBreakdown,
    TrackLabel,
    UBOResolutionStatus,
    Verdict,
    VerdictEnum,
)

# Track B thresholds — tunable per jurisdiction via regulatory engine
REVIEW_RISK_THRESHOLD = 0.50
HIGH_PRIORITY_THRESHOLD = 0.85

# Track A identity thresholds
HARD_NAME_THRESHOLD = 0.92
SOFT_NAME_THRESHOLD = 0.85
PARTIAL_NAME_LOWER = 0.70


def resolve_verdict(
    payment_id: str,
    track_a: SanctionsGateResult,
    score_breakdown: ScoreBreakdown,
    ubo_status: UBOResolutionStatus,
    policy_flags: PolicyFlags,
    jurisdiction_review_threshold: float = REVIEW_RISK_THRESHOLD,
) -> Verdict:
    """
    Two-track verdict resolution.

    Track A (deterministic) fires first — three MATCH paths:
      1. Comprehensive-sanctions jurisdiction (BLACK tier country)
      2. Identity confirmed (name >= HARD_NAME_THRESHOLD + corroborating identifier)
      3. 50% ownership rule (established chain, all percentages known)

    Track B (probabilistic) handles everything else — max verdict is REVIEW.
    INVARIANT: Track B can never produce MATCH.
    """
    R = score_breakdown.composite
    list_ver_ofac = None  # populated upstream in real impl

    # 1a — BLACK tier country: deterministic legal block (A:country-sanctions)
    if track_a.comprehensive_sanctions_jurisdiction:
        return Verdict(
            verdict=VerdictEnum.MATCH,
            track=TrackLabel.A_COUNTRY_SANCTIONS,
            cause=track_a.country_sanctions_program or "Comprehensive sanctions program",
            composite_score=R,
            priority=1.0,
            ubo_resolution_status=ubo_status,
            policy_flags=policy_flags,
            score_breakdown=score_breakdown,
        )

    # 1b — Confirmed identity match (Track A)
    if track_a.identity_confirmed:
        return Verdict(
            verdict=VerdictEnum.MATCH,
            track=TrackLabel.A_IDENTITY,
            cause=track_a.list_evidence or "Confirmed list match",
            composite_score=R,
            priority=1.0,
            ubo_resolution_status=ubo_status,
            policy_flags=policy_flags,
            score_breakdown=score_breakdown,
        )

    # 1c — 50% Rule (Track A): established ownership chain, all pcts known
    if track_a.owned_50pct_by_named_sdn:
        return Verdict(
            verdict=VerdictEnum.MATCH,
            track=TrackLabel.A_FIFTY_PCT_RULE,
            cause=track_a.ownership_path or "Entity owned ≥50% by named SDN",
            composite_score=R,
            priority=1.0,
            ubo_resolution_status=ubo_status,
            policy_flags=policy_flags,
            score_breakdown=score_breakdown,
        )

    # 2 — Partial identity match → always REVIEW (human must confirm/deny)
    if track_a.identity_partial:
        return Verdict(
            verdict=VerdictEnum.REVIEW,
            track=TrackLabel.A_PARTIAL,
            cause=track_a.list_evidence or "Partial list match — identity unconfirmed",
            composite_score=R,
            priority=R,
            ubo_resolution_status=ubo_status,
            policy_flags=policy_flags,
            score_breakdown=score_breakdown,
        )

    # 3 — UBO UNRESOLVED mandatory gate: route to REVIEW regardless of score
    if ubo_status == UBOResolutionStatus.UNRESOLVED:
        return Verdict(
            verdict=VerdictEnum.REVIEW,
            track=TrackLabel.B_RISK,
            cause="UBO chain unresolved — mandatory review gate (Section 8.6)",
            composite_score=R,
            priority=max(R, 0.60),  # elevated priority for UBO gaps
            ubo_resolution_status=ubo_status,
            policy_flags=policy_flags,
            score_breakdown=score_breakdown,
        )

    # 4 — Track B: risk score determines REVIEW vs NO_MATCH
    if R >= jurisdiction_review_threshold:
        return Verdict(
            verdict=VerdictEnum.REVIEW,
            track=TrackLabel.B_RISK,
            cause=f"Risk score {R:.3f} ≥ threshold {jurisdiction_review_threshold:.2f}",
            composite_score=R,
            priority=R,
            ubo_resolution_status=ubo_status,
            policy_flags=policy_flags,
            score_breakdown=score_breakdown,
        )

    return Verdict(
        verdict=VerdictEnum.NO_MATCH,
        track=TrackLabel.B_RISK,
        cause=f"Risk score {R:.3f} below threshold {jurisdiction_review_threshold:.2f}",
        composite_score=R,
        priority=R,
        ubo_resolution_status=ubo_status,
        policy_flags=policy_flags,
        score_breakdown=score_breakdown,
    )
