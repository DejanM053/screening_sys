"""Fiat payment screening router."""
from __future__ import annotations

import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from app.models.entities import (
    EntityType,
    Payment,
    PolicyFlags,
    SanctionsGateResult,
    ScreeningRequest,
    ScreeningResult,
    UBOResolutionStatus,
    Verdict,
    VerdictEnum,
)
from app.models.explanation import ExplanationRecord
from app.services.explanation import ExplanationTreeBuilder, NetworkContextBuilder
from app.services.scorer import RawFactors, compute_composite, entity_risk_from_metadata
from app.services.verdicts import resolve_verdict
from app.config import settings

router = APIRouter(prefix="/fiat", tags=["fiat-screening"])


async def _call_entity_resolution(name: str, country: str, entity_type: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{settings.entity_resolution_url}/match",
            json={"name": name, "country": country, "entity_type": entity_type},
        )
        resp.raise_for_status()
        return resp.json()


async def _call_graph_engine(entity_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.graph_engine_url}/analyze-network",
            json={"entity_id": entity_id},
        )
        resp.raise_for_status()
        return resp.json()


async def _call_regulatory_engine(payment: Payment) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{settings.regulatory_engine_url}/get-requirements",
            json={
                "originator_country": payment.originator_country,
                "beneficiary_country": payment.beneficiary_country,
                "amount_usd": payment.amount_usd,
                "entity_type": payment.entity_type,
                "asset_type": payment.asset_type,
                "chain": payment.chain or "",
                "token": "",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _post_audit(payment_id: str, verdict: Verdict, payment: Payment) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.audit_trail_url}/log",
                json={
                    "payment_id": payment_id,
                    "verdict": verdict.model_dump(mode="json"),
                    "payment": payment.model_dump(mode="json"),
                },
            )
    except Exception:
        pass  # audit failures must not block payment decisions


async def _enqueue_review(payment_id: str, verdict: Verdict, payment: Payment) -> None:
    """POST REVIEW verdicts to the review-queue service."""
    try:
        policy_flag_names = []
        if verdict.policy_flags.mica_compliance_risk:
            policy_flag_names.append("MiCA_COMPLIANCE_RISK")
        if verdict.policy_flags.tron_eu_corridor_review:
            policy_flag_names.append("TRON_EU_CORRIDOR_REVIEW")
        if verdict.policy_flags.pep_flag:
            policy_flag_names.append("PEP_FLAG")

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
        pass  # queue failures must not block payment decisions


async def _ingest_graph(payment_id: str, payment: Payment, er_result: dict, track_a_verdict: str) -> None:
    """Register this entity in the graph-engine so network risk can be computed."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.graph_engine_url}/ingest-entity",
                json={
                    "entity_id": payment_id,
                    "name": payment.originator_name,
                    "country": payment.originator_country,
                    "individual_score": er_result.get("top_score", 0.0),
                    "ubo_resolution_status": er_result.get("ubo_resolution_status", "FULL"),
                    "track_a_verdict": track_a_verdict,
                },
            )
    except Exception:
        pass


@router.post("/screen", response_model=ScreeningResult)
async def screen_fiat_payment(
    req: ScreeningRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> ScreeningResult:
    start = time.monotonic()
    payment = req.payment
    payment_id = payment.payment_id or str(uuid.uuid4())

    # ── Entity resolution (name match against sanctions lists) ──────────────
    try:
        er_result = await _call_entity_resolution(
            payment.originator_name,
            payment.originator_country,
            payment.entity_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Entity resolution unavailable: {exc}")

    name_composite: float = er_result.get("top_score", 0.0)
    list_evidence: Optional[str] = er_result.get("top_match_detail")
    identity_partial = name_composite >= 0.70 and name_composite < 0.92
    identity_confirmed = name_composite >= 0.92 and bool(er_result.get("corroboration"))

    track_a = SanctionsGateResult(
        identity_confirmed=identity_confirmed,
        identity_partial=identity_partial,
        name_composite=name_composite,
        list_evidence=list_evidence,
    )

    # ── Regulatory engine (jurisdiction rules + country risk) ─────────────
    try:
        reg_result = await _call_regulatory_engine(payment)
    except Exception:
        reg_result = {}

    is_black_tier = reg_result.get("auto_block", False)
    track_a.comprehensive_sanctions_jurisdiction = is_black_tier
    track_a.country_sanctions_program = reg_result.get("country_sanctions_program")

    review_threshold: float = reg_result.get("review_threshold", 0.50)
    country_risk_multiplier: float = reg_result.get("country_risk_multiplier", 1.0)
    policy_flags = PolicyFlags(
        mica_compliance_risk=reg_result.get("mica_compliance_risk", False),
        tron_eu_corridor_review=reg_result.get("tron_eu_corridor_review", False),
    )

    # ── Track B factors ────────────────────────────────────────────────────
    entity_risk_from_er = er_result.get("entity_risk_flags_score", 0.0)
    ubo_str = er_result.get("ubo_resolution_status", UBOResolutionStatus.FULL.value)
    # Use deterministic metadata-driven score; take max with entity-resolution score
    entity_risk_meta = entity_risk_from_metadata(
        amount_usd=payment.amount_usd,
        originator_country=payment.originator_country,
        beneficiary_country=payment.beneficiary_country,
        entity_type=payment.entity_type,
        country_risk_multiplier=country_risk_multiplier,
        ubo_resolution_status=ubo_str,
    )
    entity_risk_with_multiplier = max(entity_risk_from_er, entity_risk_meta)

    # Register entity in graph (fire-and-forget; graph engine uses its own verdict later)
    track_a_str = "NO_MATCH"
    if identity_confirmed:
        track_a_str = "MATCH"
    elif identity_partial:
        track_a_str = "REVIEW"
    await _ingest_graph(payment_id, payment, er_result, track_a_str)

    network_score: float = 0.0
    graph_result: dict = {}
    try:
        graph_result = await _call_graph_engine(payment_id)
        network_score = graph_result.get("network_risk_score", 0.0)
    except Exception:
        pass  # graph engine unavailable: score stays 0

    factors = RawFactors(
        identity_match=name_composite,
        behavioral_anomaly=0.0,       # populated by behavioral analysis service
        network_exposure=network_score,
        entity_risk_profile=entity_risk_with_multiplier,
        doc_integrity=0.0,            # populated by document integrity service
        historical_flag_rate=er_result.get("historical_flag_rate", 0.0),
        ml_delta=0.0,                 # ML delta: roadmap stub
    )
    score_breakdown = compute_composite(factors)

    ubo_status = UBOResolutionStatus(
        er_result.get("ubo_resolution_status", UBOResolutionStatus.FULL)
    )

    verdict = resolve_verdict(
        payment_id=payment_id,
        track_a=track_a,
        score_breakdown=score_breakdown,
        ubo_status=ubo_status,
        policy_flags=policy_flags,
        jurisdiction_review_threshold=review_threshold,
    )

    tree = ExplanationTreeBuilder.build(verdict=verdict, track_a=track_a, er_result=er_result)
    network_context = NetworkContextBuilder.build(graph_result=graph_result, verdict=verdict, entity_id=payment_id)
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

    background_tasks.add_task(_post_audit, payment_id, verdict, payment)
    if verdict.verdict == VerdictEnum.REVIEW:
        background_tasks.add_task(_enqueue_review, payment_id, verdict, payment)

    elapsed_ms = (time.monotonic() - start) * 1000
    return ScreeningResult(
        payment_id=payment_id,
        verdict=verdict,
        processing_time_ms=round(elapsed_ms, 2),
    )
