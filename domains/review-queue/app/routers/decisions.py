from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models import DecisionRequest, DecisionResult

router = APIRouter()


@router.post("/decide/{payment_id}", response_model=DecisionResult)
async def decide(payment_id: str, req: DecisionRequest, request: Request) -> DecisionResult:
    try:
        return await request.app.state.queue.decide(payment_id, req)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown payment_id '{payment_id}'")
