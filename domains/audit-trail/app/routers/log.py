"""POST /log — write-once audit record."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.logger import write_audit_records
from app.models import AuditLogRequest, AuditLogResponse

router = APIRouter(tags=["audit-trail"])


@router.post("/log", response_model=AuditLogResponse)
async def log_screening_decision(req: AuditLogRequest, request: Request) -> AuditLogResponse:
    store = request.app.state.store
    records = await write_audit_records(store, req)
    return AuditLogResponse(records=records)
