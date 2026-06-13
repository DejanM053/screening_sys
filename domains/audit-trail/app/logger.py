"""Write-once audit record logging (Section 11.4)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from app.models import AuditLogRecord, AuditLogRequest
from app.retention import compute_retention_until
from app.store import AuditLogStore


def _wallet_addresses(req: AuditLogRequest) -> List[str]:
    """Every wallet on the payment gets its own audit record so freeze-risk
    reconstruction (Section 11.4) works for either party. Falls back to
    req.wallet_address (crypto-screener, CC-05) or [None] for fiat payments."""
    addresses: List[str] = []
    if req.wallet_address:
        addresses.append(req.wallet_address)
    if req.payment:
        for key in ("originator_wallet", "beneficiary_wallet"):
            addr = req.payment.get(key)
            if addr and addr not in addresses:
                addresses.append(addr)
    return addresses or [None]  # type: ignore[list-item]


def _country_codes(req: AuditLogRequest) -> List[str]:
    if not req.payment:
        return []
    return [
        c
        for c in (req.payment.get("originator_country"), req.payment.get("beneficiary_country"))
        if c
    ]


async def write_audit_records(store: AuditLogStore, req: AuditLogRequest) -> List[AuditLogRecord]:
    verdict = req.verdict
    screened_at_raw = verdict.get("screened_at")
    if screened_at_raw:
        try:
            screened_at = datetime.fromisoformat(str(screened_at_raw).replace("Z", "+00:00"))
        except ValueError:
            screened_at = datetime.now(timezone.utc)
    else:
        screened_at = datetime.now(timezone.utc)

    countries = _country_codes(req)
    is_high_risk = bool(
        verdict.get("policy_flags", {}).get("mica_compliance_risk")
        or verdict.get("policy_flags", {}).get("tron_eu_corridor_review")
    )
    retention_until = compute_retention_until(screened_at, countries, high_risk=is_high_risk)

    records: List[AuditLogRecord] = []
    for wallet_address in _wallet_addresses(req):
        record = await store.insert(
            wallet_address=wallet_address,
            entity_id=req.entity_id,
            payment_id=req.payment_id,
            screening_result=verdict,
            verdict=verdict.get("verdict", "REVIEW"),
            list_version_ofac=verdict.get("list_version_ofac"),
            list_version_ofsi=verdict.get("list_version_ofsi"),
            algorithm_version=verdict.get("algorithm_version", "v1.2"),
            document_refs=req.document_refs,
            retention_until=retention_until,
        )
        records.append(record)
    return records
