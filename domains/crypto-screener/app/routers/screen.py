"""POST /screen-wallet (Section 10.3)."""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request

from app.config import settings
from app.models import ScreenWalletRequest, ScreenWalletResponse

logger = logging.getLogger("crypto-screener.routers.screen")

router = APIRouter(tags=["crypto-screener"])


@router.post("/screen-wallet", response_model=ScreenWalletResponse)
async def screen_wallet(req: ScreenWalletRequest, request: Request) -> ScreenWalletResponse:
    screener = request.app.state.screener
    result = await screener.screen_wallet(req)

    await _post_audit(req, result)
    return result


async def _post_audit(req: ScreenWalletRequest, result: ScreenWalletResponse) -> None:
    """Log every screening decision with wallet_address as primary key (Section 11.4)."""
    try:
        verdict = {
            "verdict": result.recommended_verdict.value,
            "track": "B:risk",
            "cause": "crypto-screener wallet screen",
            "composite_score": result.composite_score,
            "priority": result.composite_score,
            "ubo_resolution_status": result.ubo_status.value,
            "policy_flags": {
                "mica_compliance_risk": result.mica_flag,
                "tron_eu_corridor_review": result.tron_eu_corridor_flag,
                "pep_flag": False,
            },
            "algorithm_version": "v1.2",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.audit_trail_url}/log",
                json={
                    "payment_id": f"wallet-screen-{req.address}",
                    "wallet_address": req.address,
                    "entity_id": result.entity_id,
                    "verdict": verdict,
                },
            )
    except Exception as exc:  # audit failures must not block screening
        logger.warning("Audit logging unavailable: %s", exc)
