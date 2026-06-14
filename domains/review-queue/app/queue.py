"""Priority-sorted REVIEW queue (Section 12.4 Queue Dashboard)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.config import settings
from app.escalation import apply_all
from app.models import (
    Decision,
    DecisionRequest,
    DecisionResult,
    EnqueueRequest,
    QueueItem,
    QueueItemStatus,
    TransferType,
)
from app.store import QueueItemStore


class ReviewQueue:
    def __init__(self, store: QueueItemStore, audit_trail_url: Optional[str] = None):
        self._store = store
        self._audit_trail_url = audit_trail_url or settings.audit_trail_url

    async def enqueue(self, req: EnqueueRequest, now: Optional[datetime] = None) -> QueueItem:
        now = now or datetime.now(timezone.utc)
        high_priority = req.score >= settings.high_priority_threshold
        sla_hours = settings.high_priority_sla_hours if high_priority else settings.standard_sla_hours

        item = QueueItem(
            **req.model_dump(),
            enqueued_at=now,
            sla_deadline=now + timedelta(hours=sla_hours),
            status=QueueItemStatus.PENDING,
            high_priority=high_priority,
        )
        item = apply_all(item, now=now)

        await self._store.put(item.payment_id, item.model_dump_json())
        return item

    async def get(self, payment_id: str) -> Optional[QueueItem]:
        raw = await self._store.get(payment_id)
        if raw is None:
            return None
        return QueueItem.model_validate_json(raw)

    async def list_items(
        self,
        transfer_type: Optional[TransferType] = None,
        country: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        ubo_resolution_status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        status: QueueItemStatus = QueueItemStatus.PENDING,
        now: Optional[datetime] = None,
    ) -> list[QueueItem]:
        now = now or datetime.now(timezone.utc)
        items: list[QueueItem] = []

        for raw in await self._store.all():
            item = QueueItem.model_validate_json(raw)
            if item.status != status:
                continue

            item = apply_all(item, now=now)

            if transfer_type is not None and item.transfer_type != transfer_type:
                continue
            if country is not None and item.country != country:
                continue
            if min_score is not None and item.score < min_score:
                continue
            if max_score is not None and item.score > max_score:
                continue
            if ubo_resolution_status is not None and item.ubo_resolution_status != ubo_resolution_status:
                continue
            if assigned_to is not None and item.assigned_to != assigned_to:
                continue

            await self._store.put(item.payment_id, item.model_dump_json())
            items.append(item)

        items.sort(key=lambda i: i.sort_key)
        return items

    async def decide(self, payment_id: str, decision_req: DecisionRequest, now: Optional[datetime] = None) -> DecisionResult:
        item = await self.get(payment_id)
        if item is None:
            raise KeyError(payment_id)

        now = now or datetime.now(timezone.utc)

        if decision_req.decision == Decision.DEFER:
            item.sla_deadline = now + timedelta(hours=settings.standard_sla_hours)
            item.status = QueueItemStatus.PENDING
            item.escalated = False
            item.escalation_reason = None
            await self._store.put(item.payment_id, item.model_dump_json())
            await self._log_decision(item, decision_req)
            return DecisionResult(payment_id=payment_id, decision=decision_req.decision, requeued=True, item=item)

        item.status = QueueItemStatus.DECIDED
        item.assigned_to = decision_req.analyst_id
        item.decision = decision_req.decision
        item.decided_at = now
        await self._store.put(item.payment_id, item.model_dump_json())
        await self._log_decision(item, decision_req)
        return DecisionResult(payment_id=payment_id, decision=decision_req.decision, requeued=False, item=item)

    async def _log_decision(self, item: QueueItem, decision_req: DecisionRequest) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self._audit_trail_url}/log",
                    json={
                        "payment_id": item.payment_id,
                        "entity_id": item.entity_id,
                        "verdict": {
                            "decision": decision_req.decision.value,
                            "analyst_id": decision_req.analyst_id,
                            "notes": decision_req.notes,
                            "queue_item": item.model_dump(mode="json"),
                        },
                    },
                )
        except Exception:
            pass
