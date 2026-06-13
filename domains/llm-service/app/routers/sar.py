from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["sar"])


class SarDraftRequest(BaseModel):
    payment_id: str
    verdict: str
    composite_score: float
    tree: Dict[str, Any]
    payment: Dict[str, Any]
    analyst_notes: Optional[str] = None


class SarDraftResponse(BaseModel):
    payment_id: str
    draft: str


@router.post("/generate-sar-draft", response_model=SarDraftResponse)
async def generate_sar_draft(req: SarDraftRequest, request: Request) -> SarDraftResponse:
    generator = request.app.state.sar_generator
    draft = await generator.generate(
        payment_id=req.payment_id,
        verdict=req.verdict,
        composite_score=req.composite_score,
        tree=req.tree,
        payment=req.payment,
        analyst_notes=req.analyst_notes,
    )
    return SarDraftResponse(payment_id=req.payment_id, draft=draft)
