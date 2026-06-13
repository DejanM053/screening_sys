from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import Decision, DecisionRequest, EnqueueRequest, QueueItemStatus, TransferType
from app.queue import ReviewQueue
from app.store import InMemoryQueueItemStore


@pytest.fixture
def queue():
    return ReviewQueue(store=InMemoryQueueItemStore())


def _req(payment_id: str, score: float, **kwargs) -> EnqueueRequest:
    return EnqueueRequest(
        payment_id=payment_id,
        entity_id=f"ENT-{payment_id}",
        entity_name=f"Entity {payment_id}",
        score=score,
        **kwargs,
    )


async def test_enqueue_sets_high_priority_and_sla(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)

    standard = await queue.enqueue(_req("p1", 0.60), now=now)
    high = await queue.enqueue(_req("p2", 0.90), now=now)

    assert standard.high_priority is False
    assert standard.sla_deadline == now + timedelta(hours=settings.standard_sla_hours)

    assert high.high_priority is True
    assert high.sla_deadline == now + timedelta(hours=settings.high_priority_sla_hours)


async def test_list_items_sorted_by_score_desc_then_sla_asc(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)

    await queue.enqueue(_req("low", 0.55), now=now)
    await queue.enqueue(_req("high", 0.90), now=now)
    # Same score as "low" but enqueued earlier -> closer SLA deadline -> sorts first among ties
    await queue.enqueue(_req("low-urgent", 0.55), now=now - timedelta(hours=10))

    items = await queue.list_items(now=now)

    assert [i.payment_id for i in items] == ["high", "low-urgent", "low"]


async def test_network_risk_escalation_applied_on_enqueue(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)

    item = await queue.enqueue(_req("p1", 0.55, network_risk_score=0.75), now=now)

    assert item.escalated is True
    assert "noisy-OR" in item.escalation_reason


async def test_sla_breach_escalation_applied_when_listing(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    item = await queue.enqueue(_req("p1", 0.55), now=now)
    assert item.escalated is False

    later = item.sla_deadline + timedelta(minutes=1)
    items = await queue.list_items(now=later)

    assert items[0].escalated is True
    assert "SLA deadline" in items[0].escalation_reason


async def test_decide_clear_marks_decided_and_removes_from_pending(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    await queue.enqueue(_req("p1", 0.55), now=now)

    result = await queue.decide("p1", DecisionRequest(decision=Decision.CLEAR, analyst_id="analyst-1"), now=now)

    assert result.requeued is False
    assert result.item.status == QueueItemStatus.DECIDED

    pending = await queue.list_items(now=now)
    assert pending == []


async def test_decide_defer_requeues_with_extended_sla(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    item = await queue.enqueue(_req("p1", 0.55), now=now)
    original_deadline = item.sla_deadline

    result = await queue.decide(
        "p1", DecisionRequest(decision=Decision.DEFER, analyst_id="analyst-1"), now=now + timedelta(hours=1)
    )

    assert result.requeued is True
    assert result.item.status == QueueItemStatus.PENDING
    assert result.item.sla_deadline > original_deadline

    pending = await queue.list_items(now=now)
    assert [i.payment_id for i in pending] == ["p1"]


async def test_decide_unknown_payment_raises_keyerror(queue):
    with pytest.raises(KeyError):
        await queue.decide("missing", DecisionRequest(decision=Decision.CLEAR, analyst_id="analyst-1"))


async def test_list_items_filters_by_transfer_type_and_country(queue):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    await queue.enqueue(_req("internal", 0.55, transfer_type=TransferType.INTERNAL, country="GB"), now=now)
    await queue.enqueue(_req("inbound", 0.60, transfer_type=TransferType.INBOUND, country="AE"), now=now)

    gb_only = await queue.list_items(country="GB", now=now)
    assert [i.payment_id for i in gb_only] == ["internal"]

    inbound_only = await queue.list_items(transfer_type=TransferType.INBOUND, now=now)
    assert [i.payment_id for i in inbound_only] == ["inbound"]
