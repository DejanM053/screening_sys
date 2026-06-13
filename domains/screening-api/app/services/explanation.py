"""Explanation tree + network context builders — Section 7.1 (CC-06)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.entities import (
    SanctionsGateResult,
    UBOResolutionStatus,
    Verdict,
    VerdictEnum,
)
from app.models.explanation import ConnectedEntity, NetworkContext, ScoreNode
from app.services.scorer import (
    W_BEHAVIORAL,
    W_DOC_INTEGRITY,
    W_ENTITY_PROFILE,
    W_HISTORICAL,
    W_IDENTITY,
    W_NETWORK,
)
from app.services.verdicts import HARD_NAME_THRESHOLD, HIGH_PRIORITY_THRESHOLD, REVIEW_RISK_THRESHOLD

# Track A MATCH paths whose evidence is not the fuzzy name composite — these are
# deterministic legal blocks, so the sanctions_list_match evidence node is scored 1.0.
_DETERMINISTIC_MATCH_TRACKS = {"A:50pct-rule", "A:country-sanctions"}


class ExplanationTreeBuilder:
    """Builds the Section 7.1 score explanation tree for a resolved verdict."""

    @staticmethod
    def build(
        verdict: Verdict,
        track_a: SanctionsGateResult,
        er_result: Optional[Dict[str, Any]] = None,
        policy_flags_detail: Optional[Dict[str, str]] = None,
    ) -> ScoreNode:
        er_result = er_result or {}
        sb = verdict.score_breakdown

        root = ScoreNode(
            id="root",
            label="Composite Risk Score",
            score=verdict.composite_score,
            detail=(
                f"Verdict {verdict.verdict.value} via track {verdict.track.value}. "
                f"REVIEW threshold: {REVIEW_RISK_THRESHOLD:.2f}; "
                f"high-priority threshold: {HIGH_PRIORITY_THRESHOLD:.2f}."
            ),
            metadata={
                "verdict": verdict.verdict.value,
                "track": verdict.track.value,
                "cause": verdict.cause,
            },
        )

        if sb is None:
            return root

        identity_node = ScoreNode(
            id="identity_match",
            label="Identity Match Signal",
            score=sb.identity_match,
            weight=W_IDENTITY,
            weighted_contribution=W_IDENTITY * sb.identity_match,
            detail=track_a.list_evidence or "No significant name match found.",
            metadata={"match_method": "fuzzy + phonetic", "name_composite": track_a.name_composite},
        )
        for candidate in er_result.get("candidates", []):
            identity_node.children.append(
                ScoreNode(
                    id=f"list_match:{candidate.get('list_entry_id', candidate.get('list_source', 'unknown'))}",
                    label=candidate.get("list_source", "Unknown list"),
                    score=candidate.get("score", 0.0),
                    detail=f"Matched '{candidate.get('matched_name', '')}' "
                    f"at score {candidate.get('score', 0.0):.4f} "
                    f"via {', '.join(candidate.get('match_methods_used', []))}",
                    metadata={"list_entry_id": candidate.get("list_entry_id")},
                )
            )

        # CC-06 invariant: every MATCH verdict has a sanctions_list_match node
        # with score >= 0.85.
        if verdict.verdict == VerdictEnum.MATCH:
            if verdict.track.value in _DETERMINISTIC_MATCH_TRACKS:
                match_score = 1.0
                match_detail = verdict.cause
            else:
                match_score = max(sb.identity_match, track_a.name_composite, HARD_NAME_THRESHOLD)
                match_detail = track_a.list_evidence or verdict.cause
            identity_node.children.insert(
                0,
                ScoreNode(
                    id="sanctions_list_match",
                    label="Sanctions List Match",
                    score=match_score,
                    detail=match_detail,
                    metadata={"track": verdict.track.value},
                ),
            )

        behavioral_node = ScoreNode(
            id="behavioral_anomaly",
            label="Behavioral / Transaction Anomaly",
            score=sb.behavioral_anomaly,
            weight=W_BEHAVIORAL,
            weighted_contribution=W_BEHAVIORAL * sb.behavioral_anomaly,
            detail="Transaction velocity and structuring pattern analysis vs. entity baseline.",
        )

        network_node = ScoreNode(
            id="network_exposure",
            label="Network / Graph Exposure",
            score=sb.network_exposure,
            weight=W_NETWORK,
            weighted_contribution=W_NETWORK * sb.network_exposure,
            detail=(
                f"Noisy-OR network risk {sb.network_exposure:.2f}. "
                "Association with flagged neighbours routes to REVIEW — not blocked on association alone."
            ),
            metadata={"score_formula": "1 - prod(1 - p_f * 0.5^d(e,f)), capped at 3 hops"},
        )

        ubo_node = ScoreNode(
            id="ubo_resolution",
            label="UBO Resolution",
            score=None,
            detail=f"UBO resolution status: {verdict.ubo_resolution_status.value}.",
            metadata={"ubo_resolution_status": verdict.ubo_resolution_status.value},
        )
        if verdict.ubo_resolution_status == UBOResolutionStatus.UNRESOLVED:
            ubo_node.metadata["review_gate_triggered"] = True
            ubo_node.detail += " UBO chain unresolved — mandatory REVIEW gate (Section 8.6)."

        entity_profile_node = ScoreNode(
            id="entity_risk_profile",
            label="Entity Risk Profile",
            score=sb.entity_risk_profile,
            weight=W_ENTITY_PROFILE,
            weighted_contribution=W_ENTITY_PROFILE * sb.entity_risk_profile,
            detail="Entity metadata risk flags, country risk multiplier, and UBO status.",
            metadata={
                "ubo_resolution_status": verdict.ubo_resolution_status.value,
                "corporate_risk_flags": er_result.get("corporate_risk_flags", []),
            },
            children=[ubo_node],
        )

        doc_integrity_node = ScoreNode(
            id="doc_integrity",
            label="Document / Onboarding Integrity",
            score=sb.doc_integrity,
            weight=W_DOC_INTEGRITY,
            weighted_contribution=W_DOC_INTEGRITY * sb.doc_integrity,
            detail="Onboarding document verification confidence.",
        )

        historical_node = ScoreNode(
            id="historical_flag_rate",
            label="Historical Flag Rate",
            score=sb.historical_flag_rate,
            weight=W_HISTORICAL,
            weighted_contribution=W_HISTORICAL * sb.historical_flag_rate,
            detail="Beta-Binomial smoothed prior flag rate (alpha=1, beta=9).",
        )

        root.children = [
            identity_node,
            behavioral_node,
            network_node,
            entity_profile_node,
            doc_integrity_node,
            historical_node,
        ]

        if sb.ml_delta:
            root.children.append(
                ScoreNode(
                    id="ml_delta",
                    label="ML Bounded Delta",
                    score=sb.ml_delta,
                    weight=0.0,
                    weighted_contribution=sb.ml_delta,
                    detail="LightGBM bounded delta (cap 0.15). Supplementary opinion only.",
                    metadata={"informational": True},
                )
            )

        # Informational policy-flag leaf nodes — not scored, rendered in blue in the UI.
        flags = verdict.policy_flags
        policy_flags_detail = policy_flags_detail or {}
        if flags.mica_compliance_risk:
            root.children.append(
                ScoreNode(
                    id="policy_flag:mica_compliance_risk",
                    label="MiCA Compliance Risk",
                    score=None,
                    detail=policy_flags_detail.get(
                        "mica_compliance_risk",
                        "USDT transfer on an EU corridor — Tether is not MiCA-authorized. Legal review required.",
                    ),
                    metadata={"informational": True, "policy_flag": "MiCA_COMPLIANCE_RISK"},
                )
            )
        if flags.tron_eu_corridor_review:
            root.children.append(
                ScoreNode(
                    id="policy_flag:tron_eu_corridor_review",
                    label="TRON EU Corridor Review",
                    score=None,
                    detail=policy_flags_detail.get(
                        "tron_eu_corridor_review",
                        "TRON-settled transaction on an EU/UK corridor — additional due diligence flag.",
                    ),
                    metadata={"informational": True, "policy_flag": "TRON_EU_CORRIDOR_REVIEW"},
                )
            )
        if flags.pep_flag:
            root.children.append(
                ScoreNode(
                    id="policy_flag:pep_flag",
                    label="PEP Flag",
                    score=None,
                    detail=policy_flags_detail.get(
                        "pep_flag", "A politically exposed person is associated with this entity."
                    ),
                    metadata={"informational": True, "policy_flag": "PEP_FLAG"},
                )
            )

        return root


class NetworkContextBuilder:
    """Builds the Section 7.1 network_context block from a graph-engine response."""

    @staticmethod
    def build(graph_result: Optional[Dict[str, Any]], verdict: Verdict, entity_id: str) -> Optional[NetworkContext]:
        if not graph_result:
            return None

        attribution: Dict[str, float] = graph_result.get("per_neighbour_attribution", {}) or {}
        escalation = graph_result.get("escalation_decision", {}) or {}
        network_risk_score = graph_result.get("network_risk_score", 0.0)

        connected_entities = [
            ConnectedEntity(id=neighbour_id, score=contribution)
            for neighbour_id, contribution in attribution.items()
        ]

        # INVARIANT: network_escalation_applied=true can only coexist with
        # verdict == REVIEW, never MATCH (Section 6.4 guardrails).
        escalation_applied = bool(escalation.get("escalated", False)) and verdict.verdict != VerdictEnum.MATCH

        return NetworkContext(
            neighbourhood_id=f"NET-{entity_id}",
            neighbour_count=graph_result.get("flagged_neighbour_count", len(connected_entities)),
            network_risk_score=network_risk_score,
            connected_entities=connected_entities,
            network_escalation_applied=escalation_applied,
            escalation_reason=escalation.get("justification") if escalation_applied else None,
        )
