"""Audit log storage — write-once records, wallet_address as primary index (Section 11.4)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg

from app.models import AuditLogRecord


class AuditLogStore(ABC):
    @abstractmethod
    async def insert(
        self,
        *,
        wallet_address: Optional[str],
        entity_id: Optional[str],
        payment_id: str,
        screening_result: Dict[str, Any],
        verdict: str,
        list_version_ofac: Optional[str],
        list_version_ofsi: Optional[str],
        algorithm_version: str,
        document_refs: List[str],
        retention_until: Optional[datetime],
    ) -> AuditLogRecord:
        ...

    @abstractmethod
    async def by_payment_id(self, payment_id: str) -> List[AuditLogRecord]:
        ...

    @abstractmethod
    async def by_wallet_address(self, wallet_address: str) -> List[AuditLogRecord]:
        ...


class PostgresAuditLogStore(AuditLogStore):
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def insert(self, **kwargs: Any) -> AuditLogRecord:
        import json

        assert self._pool is not None
        row = await self._pool.fetchrow(
            """
            INSERT INTO audit_log (
                wallet_address, entity_id, payment_id, screening_result, verdict,
                list_version_ofac, list_version_ofsi, algorithm_version,
                document_refs, retention_until
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id, wallet_address, entity_id, payment_id, screening_timestamp,
                      screening_result, verdict, list_version_ofac, list_version_ofsi,
                      algorithm_version, document_refs, retention_until, created_at
            """,
            kwargs["wallet_address"],
            kwargs["entity_id"],
            kwargs["payment_id"],
            json.dumps(kwargs["screening_result"]),
            kwargs["verdict"],
            kwargs["list_version_ofac"],
            kwargs["list_version_ofsi"],
            kwargs["algorithm_version"],
            json.dumps(kwargs["document_refs"]),
            kwargs["retention_until"],
        )
        return _row_to_record(row)

    async def by_payment_id(self, payment_id: str) -> List[AuditLogRecord]:
        assert self._pool is not None
        rows = await self._pool.fetch(
            "SELECT * FROM audit_log WHERE payment_id = $1 ORDER BY created_at ASC", payment_id
        )
        return [_row_to_record(r) for r in rows]

    async def by_wallet_address(self, wallet_address: str) -> List[AuditLogRecord]:
        assert self._pool is not None
        rows = await self._pool.fetch(
            "SELECT * FROM audit_log WHERE wallet_address = $1 ORDER BY created_at ASC", wallet_address
        )
        return [_row_to_record(r) for r in rows]


def _row_to_record(row: asyncpg.Record) -> AuditLogRecord:
    import json

    data = dict(row)
    if isinstance(data["screening_result"], str):
        data["screening_result"] = json.loads(data["screening_result"])
    if isinstance(data["document_refs"], str):
        data["document_refs"] = json.loads(data["document_refs"])
    return AuditLogRecord(**data)


class InMemoryAuditLogStore(AuditLogStore):
    """Used in tests and as a fallback when Postgres is unavailable.

    NOTE: not write-once at the Python level — the write-once guarantee is
    enforced by the audit_log table's triggers in PostgresAuditLogStore.
    """

    def __init__(self):
        self._records: List[AuditLogRecord] = []
        self._next_id = 1

    async def insert(self, **kwargs: Any) -> AuditLogRecord:
        now = datetime.now(timezone.utc)
        record = AuditLogRecord(
            id=self._next_id,
            screening_timestamp=now,
            created_at=now,
            **kwargs,
        )
        self._records.append(record)
        self._next_id += 1
        return record

    async def by_payment_id(self, payment_id: str) -> List[AuditLogRecord]:
        return [r for r in self._records if r.payment_id == payment_id]

    async def by_wallet_address(self, wallet_address: str) -> List[AuditLogRecord]:
        return [r for r in self._records if r.wallet_address == wallet_address]
