from app.explain import LLMExplanationGenerator, _extract_factors, _extract_ubo_status
from app.ollama_client import OllamaClient

SAMPLE_TREE = {
    "id": "root",
    "label": "Composite Risk Score",
    "score": 0.64,
    "metadata": {"verdict": "REVIEW", "track": "B:risk", "cause": "Risk score 0.640 >= threshold 0.50"},
    "children": [
        {
            "id": "identity_match",
            "label": "Identity Match Signal",
            "score": 0.71,
            "weight": 0.25,
            "weighted_contribution": 0.178,
            "detail": "Matched alias on EU Consolidated List",
        },
        {
            "id": "entity_risk_profile",
            "label": "Entity Risk Profile",
            "score": 0.80,
            "weight": 0.15,
            "weighted_contribution": 0.120,
            "detail": "UAE jurisdiction, country risk multiplier 1.35",
            "metadata": {"ubo_resolution_status": "PARTIAL"},
        },
    ],
}


def test_extract_factors_returns_only_weighted_children():
    factors = _extract_factors(SAMPLE_TREE)
    assert {f["label"] for f in factors} == {"Identity Match Signal", "Entity Risk Profile"}


def test_extract_ubo_status_from_entity_risk_profile():
    assert _extract_ubo_status(SAMPLE_TREE) == "PARTIAL"


async def test_generate_falls_back_when_ollama_unreachable():
    ollama = OllamaClient(base_url="http://localhost:1", model="qwen2.5:14b", timeout_seconds=0.5)
    generator = LLMExplanationGenerator(ollama)

    explanation = await generator.generate(
        verdict="REVIEW",
        composite_score=0.64,
        tree=SAMPLE_TREE,
        network_context={
            "network_escalation_applied": True,
            "escalation_reason": "noisy-OR 0.58 from 2 connected REVIEW entities",
            "neighbour_count": 2,
            "network_risk_score": 0.58,
        },
    )

    assert "REVIEW" in explanation
    assert "Identity Match Signal" in explanation
    assert "noisy-OR" in explanation
