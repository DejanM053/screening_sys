from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["explain"])


class ExplainRequest(BaseModel):
    payment_id: str
    verdict: str
    composite_score: float
    tree: Dict[str, Any]
    network_context: Optional[Dict[str, Any]] = None


class ExplainResponse(BaseModel):
    payment_id: str
    explanation: str


@router.post("/explain", response_model=ExplainResponse)
async def explain(req: ExplainRequest, request: Request) -> ExplainResponse:
    generator = request.app.state.explanation_generator
    explanation = await generator.generate(
        verdict=req.verdict,
        composite_score=req.composite_score,
        tree=req.tree,
        network_context=req.network_context,
    )
    return ExplainResponse(payment_id=req.payment_id, explanation=explanation)
