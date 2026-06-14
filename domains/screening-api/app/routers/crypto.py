"""Crypto/stablecoin payment screening router."""
from __future__ import annotations

import time
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app.models.entities import (
    Payment,
    PolicyFlags,
    SanctionsGateResult,
    ScreeningRequest,
    ScreeningResult,
    UBOResolutionStatus,
    VerdictEnum,
)
from app.models.explanation import ExplanationRecord
from app.services.explanation import ExplanationTreeBuilder, NetworkContextBuilder
from app.services.scorer import RawFactors, compute_composite
from app.services.verdicts import resolve_verdict
from app.config import settings

router = APIRouter(prefix="/crypto", tags=["crypto-screening"])


async def _enqueue_review(payment_id: str, verdict, payment: Payment, wallet_result: dict) -> None:
    policy_flag_names = []
    if verdict.policy_flags.mica_compliance_risk:
        policy_flag_names.append("MiCA_COMPLIANCE_RISK")
    if verdict.policy_flags.tron_eu_corridor_review:
        policy_flag_names.append("TRON_EU_CORRIDOR_REVIEW")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.review_queue_url}/enqueue",
                json={
                    "payment_id": payment_id,
                    "entity_id": payment_id,
                    "entity_name": payment.originator_name,
                    "score": verdict.composite_score,
                    "country": payment.originator_country,
                    "lists_flagged": [verdict.cause] if verdict.cause else [],
                    "transfer_type": "OUTBOUND",
                    "ubo_resolution_status": verdict.ubo_resolution_status.value,
                    "policy_flags": policy_flag_names,
                    "amount_usd": payment.amount_usd,
                    "track": verdict.track.value,
                },
            )
    except Exception:
        pass


class CryptoScreenRequest(BaseModel):
    payment: Payment
    stablecoin: str = "USDT"
    analyst_id: str | None = None


@router.post("/screen", response_model=ScreeningResult)
async def screen_crypto_payment(
    req: CryptoScreenRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> ScreeningResult:
    start = time.monotonic()
    payment = req.payment
    payment_id = payment.payment_id or str(uuid.uuid4())

    if not payment.originator_wallet or not payment.chain:
        raise HTTPException(status_code=422, detail="Crypto screening requires wallet address and chain")

    # ── Wallet screening via crypto-screener domain ────────────────────────
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            wallet_resp = await client.post(
                f"{settings.crypto_screener_url}/screen-wallet",
                json={
                    "address": payment.originator_wallet,
                    "chain": payment.chain,
                    "stablecoin": req.stablecoin,
                    "amount_usd": payment.amount_usd,
                    "counterparty_address": payment.beneficiary_wallet or "",
                    "corridor": f"{payment.originator_country}->{payment.beneficiary_country}",
                },
            )
            wallet_resp.raise_for_status()
            wallet_result = wallet_resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Crypto screener unavailable: {exc}")

    # ── Build Track A from wallet screening results ────────────────────────
    track_a = SanctionsGateResult(
        identity_confirmed=wallet_result.get("ofac_match", False),
        comprehensive_sanctions_jurisdiction=wallet_result.get("country_block", False),
        country_sanctions_program=wallet_result.get("country_sanctions_program"),
    )

    if wallet_result.get("issuer_frozen", False):
        track_a.identity_confirmed = True
        track_a.list_evidence = "Address frozen by stablecoin issuer (Tether/Circle blacklist)"

    # ── Policy flags ───────────────────────────────────────────────────────
    policy_flags = PolicyFlags(
        mica_compliance_risk=wallet_result.get("mica_flag", False),
        tron_eu_corridor_review=wallet_result.get("tron_eu_corridor_flag", False),
    )

    # ── Track B risk score (crypto domain) ────────────────────────────────
    ubo_status = UBOResolutionStatus(
        wallet_result.get("ubo_status", UBOResolutionStatus.FULL)
    )

    factors = RawFactors(
        identity_match=wallet_result.get("ofac_score", 0.0),
        behavioral_anomaly=wallet_result.get("volume_anomaly_score", 0.0),
        network_exposure=wallet_result.get("hop_score", 0.0),
        entity_risk_profile=wallet_result.get("entity_risk_score", 0.0),
        doc_integrity=0.0,
        historical_flag_rate=wallet_result.get("historical_flag_rate", 0.0),
    )
    score_breakdown = compute_composite(factors)

    verdict = resolve_verdict(
        payment_id=payment_id,
        track_a=track_a,
        score_breakdown=score_breakdown,
        ubo_status=ubo_status,
        policy_flags=policy_flags,
    )

    tree = ExplanationTreeBuilder.build(verdict=verdict, track_a=track_a, er_result={})
    network_context = NetworkContextBuilder.build(graph_result=None, verdict=verdict, entity_id=payment_id)
    verdict.explanation_tree = tree.model_dump()

    explanation_record = ExplanationRecord(
        payment_id=payment_id,
        verdict=verdict.verdict.value,
        track=verdict.track.value,
        composite_score=verdict.composite_score,
        tree=tree,
        network_context=network_context,
        payment=payment.model_dump(mode="json"),
        screened_at=verdict.screened_at.isoformat(),
    )
    await request.app.state.explanation_store.put(payment_id, explanation_record)

    if verdict.verdict == VerdictEnum.REVIEW:
        background_tasks.add_task(_enqueue_review, payment_id, verdict, payment, wallet_result)

    elapsed_ms = (time.monotonic() - start) * 1000
    return ScreeningResult(
        payment_id=payment_id,
        verdict=verdict,
        processing_time_ms=round(elapsed_ms, 2),
    )
