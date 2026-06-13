"""Admin/test utilities for seeding the KYB wallet registry and OFAC list."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.models import KYBRecord

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/kyb-registry/{address}")
async def register_kyb_wallet(address: str, record: KYBRecord, request: Request) -> dict:
    await request.app.state.kyb_registry.register(address, record)
    return {"status": "registered", "address": address}


@router.post("/ofac-wallets")
async def load_ofac_wallets(addresses: list[str], request: Request) -> dict:
    await request.app.state.ofac_screener.load(addresses)
    return {"status": "loaded", "count": len(addresses)}
