"""Bayesian noisy-OR network risk scorer (Section 6.4, CC-03).

INVARIANT: network risk can escalate to REVIEW only, never to MATCH.
The only graph path to MATCH is the deterministic 50% ownership rule (Track A),
handled separately in the screening-api verdict engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

LAMBDA = 0.5          # per-hop decay constant
MAX_HOPS = 3          # max traversal depth
REVIEW_THRESHOLD = 0.50


@dataclass
class FlaggedNeighbour:
    neighbour_id: str
    neighbour_name: str
    hop_distance: int
    p_f: float          # 1.0 for confirmed SDN; risk_score for REVIEW nodes
    track_a_match: bool = False


@dataclass
class EscalationDecision:
    escalated: bool
    new_verdict: str    # REVIEW | NO_MATCH — never MATCH (enforced by ceiling)
    priority_boost: bool
    justification: str
    network_risk_score: float
    attribution: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assert self.new_verdict != "MATCH", (
            "EscalationEngine ceiling violated: network risk can never produce MATCH"
        )


class NetworkRiskScorer:
    """
    Implements noisy-OR network risk from Section 6.4 (Option A).

    network_risk(e) = 1 - ∏_f [ 1 - p_f × lambda^d(e,f) ]

    Per-neighbour marginal contribution (leave-one-out):
        contribution_f = risk_with_all - risk_excluding_f
    """

    def compute(
        self, flagged_neighbours: List[FlaggedNeighbour]
    ) -> tuple[float, Dict[str, float]]:
        if not flagged_neighbours:
            return 0.0, {}

        def noisy_or(neighbours: List[FlaggedNeighbour]) -> float:
            product = 1.0
            for n in neighbours:
                d = min(n.hop_distance, MAX_HOPS)
                taint = n.p_f * (LAMBDA ** d)
                product *= 1.0 - taint
            return 1.0 - product

        total_risk = noisy_or(flagged_neighbours)

        # Leave-one-out attribution
        attribution: Dict[str, float] = {}
        for i, neighbour in enumerate(flagged_neighbours):
            without = [n for j, n in enumerate(flagged_neighbours) if j != i]
            risk_without = noisy_or(without) if without else 0.0
            attribution[neighbour.neighbour_id] = round(total_risk - risk_without, 4)

        return round(total_risk, 4), attribution


class EscalationEngine:
    """
    Applies network risk to verdict — CEILING: output is never MATCH.
    """

    def __init__(self, review_threshold: float = REVIEW_THRESHOLD):
        self.review_threshold = review_threshold

    def evaluate(
        self,
        network_risk_score: float,
        attribution: Dict[str, float],
        individual_verdict: str,
        neighbours: List[FlaggedNeighbour],
    ) -> EscalationDecision:
        top_contributors = sorted(
            attribution.items(), key=lambda x: x[1], reverse=True
        )[:3]

        contrib_text = "; ".join(
            f"{nid} (marginal {contrib:.3f})"
            for nid, contrib in top_contributors
        )
        justification = (
            f"Network risk {network_risk_score:.3f} (noisy-OR, λ={LAMBDA}): {contrib_text}. "
            f"Routed to REVIEW — not blocked on association alone."
        )

        escalated = (
            network_risk_score >= self.review_threshold
            and individual_verdict == "NO_MATCH"
        )
        priority_boost = (
            network_risk_score >= 0.70
            and individual_verdict == "REVIEW"
        )

        new_verdict = "REVIEW" if (escalated or individual_verdict == "REVIEW") else "NO_MATCH"

        # Hard ceiling: network layer can never produce MATCH
        assert new_verdict != "MATCH"

        return EscalationDecision(
            escalated=escalated,
            new_verdict=new_verdict,
            priority_boost=priority_boost,
            justification=justification,
            network_risk_score=network_risk_score,
            attribution=attribution,
        )
