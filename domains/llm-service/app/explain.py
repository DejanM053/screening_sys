"""Score explanation generation (Section 7, CC-06)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ollama_client import OllamaClient


def _extract_factors(tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    factors = []
    for child in tree.get("children", []):
        if child.get("weight"):
            factors.append({
                "label": child.get("label"),
                "score": child.get("score"),
                "weight": child.get("weight"),
                "weighted_contribution": child.get("weighted_contribution"),
                "detail": child.get("detail", ""),
            })
    return factors


def _extract_ubo_status(tree: Dict[str, Any]) -> Optional[str]:
    for child in tree.get("children", []):
        if child.get("id") == "entity_risk_profile":
            return child.get("metadata", {}).get("ubo_resolution_status")
    return None


def _build_prompt(
    verdict: str,
    composite_score: float,
    tree: Dict[str, Any],
    network_context: Optional[Dict[str, Any]],
) -> str:
    factors = _extract_factors(tree)
    ubo_status = _extract_ubo_status(tree)
    factors_text = "; ".join(
        f"{f['label']} (score {f['score']:.2f}, weight {f['weight']:.2f}, "
        f"contribution {f['weighted_contribution']:.3f}): {f['detail']}"
        for f in factors
    )

    network_text = ""
    if network_context and network_context.get("network_escalation_applied"):
        network_text = (
            f"\nNetwork context: {network_context.get('escalation_reason', '')} "
            f"({network_context.get('neighbour_count', 0)} connected entities, "
            f"network risk {network_context.get('network_risk_score', 0):.2f})."
        )

    return (
        "You are a compliance analyst reviewing a KYB (business) screening result. "
        f"Explain why this payment received a {verdict} verdict. "
        f"Score: {composite_score:.2f}. Key factors: {factors_text}. "
        f"UBO status: {ubo_status}.{network_text} "
        "Write for a regulator who may read this in 2 years. Be precise, "
        "cite specific list names and match scores. Do not speculate."
    )


def _fallback_explanation(
    verdict: str,
    composite_score: float,
    tree: Dict[str, Any],
    network_context: Optional[Dict[str, Any]],
) -> str:
    factors = sorted(_extract_factors(tree), key=lambda f: f["weighted_contribution"], reverse=True)
    ubo_status = _extract_ubo_status(tree)

    top_factors = ", ".join(
        f"{f['label']} (score {f['score']:.2f}, contributing {f['weighted_contribution']:.3f})"
        for f in factors[:3]
    )

    cause = tree.get("metadata", {}).get("cause", "")
    paragraphs = [
        f"This payment received a {verdict} verdict with a composite risk score of "
        f"{composite_score:.2f}. {cause}".strip(),
        f"The leading contributing factors were: {top_factors}. UBO resolution status: {ubo_status}.",
    ]
    if network_context and network_context.get("network_escalation_applied"):
        paragraphs.append(
            f"Network context: {network_context.get('escalation_reason', '')}"
        )
    return "\n\n".join(paragraphs)


class LLMExplanationGenerator:
    def __init__(self, ollama: OllamaClient) -> None:
        self.ollama = ollama

    async def generate(
        self,
        verdict: str,
        composite_score: float,
        tree: Dict[str, Any],
        network_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            prompt = _build_prompt(verdict, composite_score, tree, network_context)
            response = await self.ollama.generate(prompt)
            if response:
                return response
        except Exception:
            pass
        return _fallback_explanation(verdict, composite_score, tree, network_context)
