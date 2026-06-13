"""Unit tests for the CC-06 explanation tree / network context builders."""
from app.models.entities import (
    PolicyFlags,
    SanctionsGateResult,
    UBOResolutionStatus,
    VerdictEnum,
)
from app.services.explanation import ExplanationTreeBuilder, NetworkContextBuilder
from app.services.scorer import RawFactors, compute_composite
from app.services.verdicts import resolve_verdict


def _verdict(track_a=None, ubo_status=UBOResolutionStatus.FULL, policy_flags=None, factors=None):
    track_a = track_a or SanctionsGateResult()
    policy_flags = policy_flags or PolicyFlags()
    factors = factors or RawFactors()
    score_breakdown = compute_composite(factors)
    verdict = resolve_verdict(
        payment_id="p1",
        track_a=track_a,
        score_breakdown=score_breakdown,
        ubo_status=ubo_status,
        policy_flags=policy_flags,
    )
    return verdict, track_a


def _find(node, node_id):
    if node.id == node_id:
        return node
    for child in node.children:
        found = _find(child, node_id)
        if found is not None:
            return found
    return None


def test_match_via_identity_has_sanctions_list_match_node_ge_85():
    track_a = SanctionsGateResult(identity_confirmed=True, name_composite=0.95, list_evidence="OFAC SDN match")
    verdict, track_a = _verdict(track_a=track_a)
    assert verdict.verdict == VerdictEnum.MATCH

    tree = ExplanationTreeBuilder.build(verdict, track_a)
    node = _find(tree, "sanctions_list_match")
    assert node is not None
    assert node.score >= 0.85


def test_match_via_50pct_rule_has_sanctions_list_match_node_ge_85():
    track_a = SanctionsGateResult(owned_50pct_by_named_sdn=True, ownership_path="X->Y->[SDN]")
    verdict, track_a = _verdict(track_a=track_a)
    assert verdict.verdict == VerdictEnum.MATCH

    tree = ExplanationTreeBuilder.build(verdict, track_a)
    node = _find(tree, "sanctions_list_match")
    assert node is not None
    assert node.score >= 0.85


def test_match_via_country_sanctions_has_sanctions_list_match_node_ge_85():
    track_a = SanctionsGateResult(comprehensive_sanctions_jurisdiction=True, country_sanctions_program="OFAC Iran NSRP")
    verdict, track_a = _verdict(track_a=track_a)
    assert verdict.verdict == VerdictEnum.MATCH

    tree = ExplanationTreeBuilder.build(verdict, track_a)
    node = _find(tree, "sanctions_list_match")
    assert node is not None
    assert node.score >= 0.85


def test_no_match_has_no_sanctions_list_match_node():
    verdict, track_a = _verdict()
    assert verdict.verdict == VerdictEnum.NO_MATCH

    tree = ExplanationTreeBuilder.build(verdict, track_a)
    assert _find(tree, "sanctions_list_match") is None


def test_every_ubo_node_includes_resolution_status():
    for status in UBOResolutionStatus:
        verdict, track_a = _verdict(ubo_status=status)
        tree = ExplanationTreeBuilder.build(verdict, track_a)
        ubo_node = _find(tree, "ubo_resolution")
        assert ubo_node is not None
        assert ubo_node.metadata["ubo_resolution_status"] == status.value


def test_unresolved_ubo_triggers_review_gate_flag_in_tree():
    verdict, track_a = _verdict(ubo_status=UBOResolutionStatus.UNRESOLVED)
    assert verdict.verdict == VerdictEnum.REVIEW

    tree = ExplanationTreeBuilder.build(verdict, track_a)
    ubo_node = _find(tree, "ubo_resolution")
    assert ubo_node.metadata.get("review_gate_triggered") is True


def test_network_context_escalation_never_applied_on_match():
    track_a = SanctionsGateResult(identity_confirmed=True, name_composite=0.95, list_evidence="OFAC SDN match")
    verdict, _ = _verdict(track_a=track_a)
    assert verdict.verdict == VerdictEnum.MATCH

    graph_result = {
        "network_risk_score": 0.7,
        "per_neighbour_attribution": {"ENT-1": 0.3},
        "escalation_decision": {"escalated": True, "justification": "noisy-OR 0.7 from confirmed SDN neighbour"},
        "flagged_neighbour_count": 1,
    }
    ctx = NetworkContextBuilder.build(graph_result, verdict, "ENT-MAIN")
    assert ctx.network_escalation_applied is False
    assert ctx.escalation_reason is None
    assert verdict.verdict == VerdictEnum.MATCH


def test_network_context_escalation_applied_on_review():
    verdict, _ = _verdict(factors=RawFactors(
        identity_match=0.6, behavioral_anomaly=0.6, network_exposure=0.6,
        entity_risk_profile=0.6, doc_integrity=0.6, historical_flag_rate=0.6,
    ))
    assert verdict.verdict == VerdictEnum.REVIEW

    graph_result = {
        "network_risk_score": 0.6,
        "per_neighbour_attribution": {"ENT-1": 0.3},
        "escalation_decision": {"escalated": True, "justification": "noisy-OR 0.6 from 1 REVIEW neighbour at 1 hop"},
        "flagged_neighbour_count": 1,
    }
    ctx = NetworkContextBuilder.build(graph_result, verdict, "ENT-MAIN")
    assert ctx.network_escalation_applied is True
    assert "noisy-OR" in ctx.escalation_reason
    assert ctx.connected_entities[0].id == "ENT-1"


def test_network_context_none_when_no_graph_result():
    verdict, _ = _verdict()
    assert NetworkContextBuilder.build(None, verdict, "ENT-MAIN") is None
    assert NetworkContextBuilder.build({}, verdict, "ENT-MAIN") is None


def test_policy_flag_nodes_are_informational_and_unscored():
    policy_flags = PolicyFlags(mica_compliance_risk=True, tron_eu_corridor_review=True, pep_flag=True)
    verdict, track_a = _verdict(policy_flags=policy_flags, factors=RawFactors(network_exposure=0.6))

    tree = ExplanationTreeBuilder.build(verdict, track_a)
    for flag_id in (
        "policy_flag:mica_compliance_risk",
        "policy_flag:tron_eu_corridor_review",
        "policy_flag:pep_flag",
    ):
        node = _find(tree, flag_id)
        assert node is not None
        assert node.metadata["informational"] is True
        assert node.score is None


def test_root_children_cover_six_factors_with_correct_weights():
    verdict, track_a = _verdict(factors=RawFactors(
        identity_match=0.5, behavioral_anomaly=0.5, network_exposure=0.5,
        entity_risk_profile=0.5, doc_integrity=0.5, historical_flag_rate=0.5,
    ))
    tree = ExplanationTreeBuilder.build(verdict, track_a)
    weights = {c.id: c.weight for c in tree.children if c.weight}
    assert weights == {
        "identity_match": 0.25,
        "behavioral_anomaly": 0.20,
        "network_exposure": 0.20,
        "entity_risk_profile": 0.15,
        "doc_integrity": 0.10,
        "historical_flag_rate": 0.10,
    }
    for child in tree.children:
        if child.weight:
            assert child.weighted_contribution == round(child.weight * child.score, 10)
