"""GET /export/{payment_id} and GET /wallet/{wallet_address} (Section 11.4)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.export import build_export, render_pdf
from app.models import AuditLogResponse, ExportResponse

router = APIRouter(tags=["audit-trail"])


@router.get("/export/{payment_id}", response_model=ExportResponse)
async def export_payment(payment_id: str, request: Request, format: str = "json") -> Response:
    store = request.app.state.store
    records = await store.by_payment_id(payment_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"No audit records found for payment {payment_id}")

    export = build_export(payment_id, records)

    if format == "pdf":
        pdf_bytes = render_pdf(export)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="audit-{payment_id}.pdf"'},
        )

    return Response(content=export.model_dump_json(), media_type="application/json")


@router.get("/wallet/{wallet_address}", response_model=AuditLogResponse)
async def export_wallet_history(wallet_address: str, request: Request) -> AuditLogResponse:
    """Wallet-indexed audit history — used for Tether freeze-risk reconstruction (Section 11.4)."""
    store = request.app.state.store
    records = await store.by_wallet_address(wallet_address)
    return AuditLogResponse(records=records)
