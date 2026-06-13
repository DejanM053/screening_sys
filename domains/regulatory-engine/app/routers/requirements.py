"""POST /get-requirements (CC-04 §6)."""
from __future__ import annotations

from fastapi import APIRouter

from app.models import GetRequirementsResponse, RegulatoryPaymentContext
from app.router_engine import RegulatoryEngineRouter

router = APIRouter(tags=["regulatory-engine"])
_engine = RegulatoryEngineRouter()


@router.post("/get-requirements", response_model=GetRequirementsResponse)
async def get_requirements(payment: RegulatoryPaymentContext) -> GetRequirementsResponse:
    return _engine.get_requirements(payment)
