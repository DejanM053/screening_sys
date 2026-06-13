"""Suspicious Activity Report (SAR) draft generation (CC-06)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.explain import _extract_factors, _extract_ubo_status
from app.ollama_client import OllamaClient


def _build_prompt(
    payment_id: str,
    verdict: str,
    composite_score: float,
    tree: Dict[str, Any],
    payment: Dict[str, Any],
    analyst_notes: Optional[str],
) -> str:
    factors = sorted(_extract_factors(tree), key=lambda f: f["weighted_contribution"], reverse=True)
    factors_text = "; ".join(
        f"{f['label']}: score {f['score']:.2f}, contribution {f['weighted_contribution']:.3f} — {f['detail']}"
        for f in factors
    )
    ubo_status = _extract_ubo_status(tree)

    return (
        "You are a compliance analyst drafting a Suspicious Activity Report (SAR) "
        "for a regulator (FinCEN/FCA format) describing a KYB (business) payment screening result. "
        f"Payment ID: {payment_id}. Verdict: {verdict}. Composite risk score: {composite_score:.2f}. "
        f"Originator: {payment.get('originator_name')} ({payment.get('originator_country')}). "
        f"Beneficiary: {payment.get('beneficiary_name')} ({payment.get('beneficiary_country')}). "
        f"Amount: {payment.get('amount_usd')} USD. "
        f"UBO resolution status: {ubo_status}. "
        f"Contributing factors: {factors_text}. "
        f"Analyst notes: {analyst_notes or 'none'}. "
        "Structure the draft with sections: Subject Information, Suspicious Activity Summary, "
        "Supporting Evidence, and Analyst Notes. Be precise, cite specific scores and list names, "
        "and do not speculate beyond the evidence provided."
    )


def _fallback_draft(
    payment_id: str,
    verdict: str,
    composite_score: float,
    tree: Dict[str, Any],
    payment: Dict[str, Any],
    analyst_notes: Optional[str],
) -> str:
    factors = sorted(_extract_factors(tree), key=lambda f: f["weighted_contribution"], reverse=True)
    ubo_status = _extract_ubo_status(tree)
    factors_lines = "\n".join(
        f"  - {f['label']}: score {f['score']:.2f}, contribution {f['weighted_contribution']:.3f} — {f['detail']}"
        for f in factors
    )

    return (
        f"SUBJECT INFORMATION\n"
        f"Payment ID: {payment_id}\n"
        f"Originator: {payment.get('originator_name')} ({payment.get('originator_country')})\n"
        f"Beneficiary: {payment.get('beneficiary_name')} ({payment.get('beneficiary_country')})\n"
        f"Amount: {payment.get('amount_usd')} USD\n"
        f"UBO resolution status: {ubo_status}\n\n"
        f"SUSPICIOUS ACTIVITY SUMMARY\n"
        f"Verdict: {verdict}. Composite risk score: {composite_score:.2f}.\n"
        f"{tree.get('metadata', {}).get('cause', '')}\n\n"
        f"SUPPORTING EVIDENCE\n"
        f"{factors_lines}\n\n"
        f"ANALYST NOTES\n"
        f"{analyst_notes or 'none'}"
    )


class SarDraftGenerator:
    def __init__(self, ollama: OllamaClient) -> None:
        self.ollama = ollama

    async def generate(
        self,
        payment_id: str,
        verdict: str,
        composite_score: float,
        tree: Dict[str, Any],
        payment: Dict[str, Any],
        analyst_notes: Optional[str] = None,
    ) -> str:
        try:
            prompt = _build_prompt(payment_id, verdict, composite_score, tree, payment, analyst_notes)
            response = await self.ollama.generate(prompt)
            if response:
                return response
        except Exception:
            pass
        return _fallback_draft(payment_id, verdict, composite_score, tree, payment, analyst_notes)
