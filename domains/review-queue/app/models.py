from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TransferType(str, Enum):
    INTERNAL = "INTERNAL"    # KYB <-> KYB
    OUTBOUND = "OUTBOUND"    # KYB -> external
    INBOUND = "INBOUND"      # external -> KYB


class QueueItemStatus(str, Enum):
    PENDING = "PENDING"
    DECIDED = "DECIDED"


class Decision(str, Enum):
    CLEAR = "CLEAR"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    REQUEST_INFO = "REQUEST_INFO"
    DEFER = "DEFER"


class EnqueueRequest(BaseModel):
    payment_id: str
    entity_id: str
    entity_name: str
    score: float = Field(ge=0.0, le=1.0)
    country: Optional[str] = None
    lists_flagged: List[str] = Field(default_factory=list)
    transfer_type: TransferType = TransferType.OUTBOUND
    ubo_resolution_status: Optional[str] = None
    policy_flags: List[str] = Field(default_factory=list)
    network_risk_score: Optional[float] = None
    network_escalation_applied: bool = False
    amount_usd: Optional[float] = None
    track: Optional[str] = None


class QueueItem(EnqueueRequest):
    enqueued_at: datetime
    sla_deadline: datetime
    status: QueueItemStatus = QueueItemStatus.PENDING
    high_priority: bool = False
    escalated: bool = False
    escalation_reason: Optional[str] = None
    assigned_to: Optional[str] = None
    decision: Optional[Decision] = None
    decided_at: Optional[datetime] = None

    @property
    def sort_key(self) -> tuple:
        """Priority sort: score DESC, then SLA deadline ASC (most urgent first)."""
        return (-self.score, self.sla_deadline)


class DecisionRequest(BaseModel):
    decision: Decision
    analyst_id: str
    notes: Optional[str] = None


class DecisionResult(BaseModel):
    payment_id: str
    decision: Decision
    requeued: bool
    item: Optional[QueueItem] = None
