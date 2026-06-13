"""Pydantic models for the audit-trail service."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuditLogRequest(BaseModel):
    """Body of POST /log.

    Either pass `wallet_address`/`entity_id` explicitly (crypto-screener,
    CC-05), or pass `payment` (the full Payment dict from screening-api) and
    wallet addresses are derived from originator_wallet/beneficiary_wallet —
    one audit record is written per distinct wallet address so freeze-risk
    reconstruction (Section 11.4) works for either party.
    """

    payment_id: str
    verdict: Dict[str, Any]
    payment: Optional[Dict[str, Any]] = None
    wallet_address: Optional[str] = None
    entity_id: Optional[str] = None
    document_refs: List[str] = Field(default_factory=list)


class AuditLogRecord(BaseModel):
    id: int
    wallet_address: Optional[str] = None
    entity_id: Optional[str] = None
    payment_id: str
    screening_timestamp: datetime
    screening_result: Dict[str, Any]
    verdict: str
    list_version_ofac: Optional[str] = None
    list_version_ofsi: Optional[str] = None
    algorithm_version: str
    document_refs: List[str] = Field(default_factory=list)
    retention_until: Optional[datetime] = None
    created_at: datetime


class AuditLogResponse(BaseModel):
    records: List[AuditLogRecord]


class ExportResponse(BaseModel):
    payment_id: str
    records: List[AuditLogRecord]
    generated_at: datetime
