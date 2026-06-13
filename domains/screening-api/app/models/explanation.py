"""Score explanation graph models — Section 7.1 (CC-06)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScoreNode(BaseModel):
    id: str
    label: str
    score: Optional[float] = None
    weight: float = 0.0
    weighted_contribution: float = 0.0
    detail: str = ""
    children: List["ScoreNode"] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


ScoreNode.model_rebuild()


class ConnectedEntity(BaseModel):
    id: str
    score: float = 0.0
    shared_attribute: Optional[str] = None
    hop_distance: Optional[int] = None


class NetworkContext(BaseModel):
    neighbourhood_id: str
    neighbour_count: int
    network_risk_score: float = 0.0
    connected_entities: List[ConnectedEntity] = Field(default_factory=list)
    network_escalation_applied: bool = False
    escalation_reason: Optional[str] = None


class ExplanationRecord(BaseModel):
    """What is persisted per payment for later retrieval by GET /explanation/{payment_id}."""
    payment_id: str
    verdict: str
    track: str
    composite_score: float
    tree: ScoreNode
    network_context: Optional[NetworkContext] = None
    payment: Dict[str, Any] = Field(default_factory=dict)
    llm_explanation: Optional[str] = None
    screened_at: str = ""


class ExplanationResponse(BaseModel):
    payment_id: str
    verdict: str
    track: str
    composite_score: float
    tree: ScoreNode
    network_context: Optional[NetworkContext] = None
    payment: Dict[str, Any] = Field(default_factory=dict)
    llm_explanation: Optional[str] = None
    screened_at: str = ""


class SarDraftRequest(BaseModel):
    payment_id: str
    analyst_notes: Optional[str] = None


class SarDraftResponse(BaseModel):
    payment_id: str
    draft: str
