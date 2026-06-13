"""Explanation graph API — Section 7, CC-06."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.models.explanation import ExplanationResponse, SarDraftRequest, SarDraftResponse

router = APIRouter(tags=["explanation"])


@router.get("/explanation/{payment_id}", response_model=ExplanationResponse)
async def get_explanation(payment_id: str, request: Request) -> ExplanationResponse:
    store = request.app.state.explanation_store
    record = await store.get(payment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No explanation found for this payment_id")

    llm_explanation = record.llm_explanation
    if llm_explanation is None:
        llm_explanation = await _call_llm_explain(record)
        if llm_explanation is not None:
            record.llm_explanation = llm_explanation
            await store.put(payment_id, record)

    return ExplanationResponse(
        payment_id=record.payment_id,
        verdict=record.verdict,
        track=record.track,
        composite_score=record.composite_score,
        tree=record.tree,
        network_context=record.network_context,
        payment=record.payment,
        llm_explanation=llm_explanation,
        screened_at=record.screened_at,
    )


@router.post("/generate-sar-draft", response_model=SarDraftResponse)
async def generate_sar_draft(req: SarDraftRequest, request: Request) -> SarDraftResponse:
    store = request.app.state.explanation_store
    record = await store.get(req.payment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No explanation found for this payment_id")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.llm_service_url}/generate-sar-draft",
                json={
                    "payment_id": record.payment_id,
                    "verdict": record.verdict,
                    "composite_score": record.composite_score,
                    "tree": record.tree.model_dump(),
                    "payment": record.payment,
                    "analyst_notes": req.analyst_notes,
                },
            )
            resp.raise_for_status()
            draft = resp.json().get("draft", "")
    except Exception:
        raise HTTPException(status_code=502, detail="LLM service unavailable for SAR draft generation")

    return SarDraftResponse(payment_id=req.payment_id, draft=draft)


async def _call_llm_explain(record) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.llm_service_url}/explain",
                json={
                    "payment_id": record.payment_id,
                    "verdict": record.verdict,
                    "composite_score": record.composite_score,
                    "tree": record.tree.model_dump(),
                    "network_context": record.network_context.model_dump() if record.network_context else None,
                },
            )
            resp.raise_for_status()
            return resp.json().get("explanation")
    except Exception:
        return None
