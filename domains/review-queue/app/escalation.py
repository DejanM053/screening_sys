"""Auto-escalation rules for queued REVIEW items.

Per Section 6.4, escalation here can only raise queue priority / mark an
item as escalated for senior attention — it never changes the verdict class.
Every item in this queue is already REVIEW; escalation is about urgency,
not re-deciding the case.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.models import QueueItem


def apply_network_escalation(item: QueueItem) -> QueueItem:
    """Network risk >= threshold raises priority (Section 6.4 EscalationEngine)."""
    if item.escalated:
        return item

    if item.network_risk_score is not None and item.network_risk_score >= settings.network_priority_boost_threshold:
        item.escalated = True
        item.escalation_reason = (
            f"Network risk {item.network_risk_score:.2f} >= "
            f"{settings.network_priority_boost_threshold:.2f} (noisy-OR) — priority raised, verdict remains REVIEW"
        )
    return item


def apply_sla_escalation(item: QueueItem, now: datetime | None = None) -> QueueItem:
    """SLA breach raises priority for senior attention."""
    if item.escalated:
        return item

    now = now or datetime.now(timezone.utc)
    if now >= item.sla_deadline:
        item.escalated = True
        item.escalation_reason = f"SLA deadline {item.sla_deadline.isoformat()} breached"
    return item


def apply_all(item: QueueItem, now: datetime | None = None) -> QueueItem:
    item = apply_network_escalation(item)
    item = apply_sla_escalation(item, now=now)
    return item
