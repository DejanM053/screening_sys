"""Graph Engine Service — networkx in-memory graph (Day-1, no Neo4j required).

Synthetic graph seeded at startup (Section 6.4 worked example):
  SDN-OFAC-001   Viktor Bout              confirmed MATCH  p=1.0
  ENT-DEMO-002   Gulf Holdings Ltd        REVIEW           score=0.61
  ENT-DEMO-003   Thames Import Solutions  REVIEW           score=0.60

Pre-seeded edges:
  ENT-DEMO-002 ── director ──> ENT-DEMO-003

New entities/edges are added dynamically via /ingest-entity and /add-relationship.
Entity being analysed sees SDN-OFAC-001 and ENT-DEMO-002 at 1 hop (after seed),
ENT-DEMO-003 at 2 hops.

noisy-OR for an entity linked to all three:
  1 - (1 - 1.0×0.5¹) × (1 - 0.61×0.5¹) × (1 - 0.60×0.25) ≈ 0.705
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

import networkx as nx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.network_risk import EscalationEngine, FlaggedNeighbour, NetworkRiskScorer

REVIEW_THRESHOLD = 0.50

# ── Shared in-memory graph (thread-safe via lock for sync networkx calls) ──────
_lock = threading.Lock()
_graph: nx.Graph = nx.Graph()


def _seed_graph() -> None:
    """Seed the synthetic demo graph at startup."""
    _graph.add_node(
        "SDN-OFAC-001",
        name="Viktor Bout",
        country="RU",
        track_a_verdict="MATCH",
        risk_score=1.0,
    )
    _graph.add_node(
        "ENT-DEMO-002",
        name="Gulf Holdings Ltd",
        country="AE",
        track_a_verdict="REVIEW",
        risk_score=0.61,
    )
    _graph.add_node(
        "ENT-DEMO-003",
        name="Thames Import Solutions Ltd",
        country="GB",
        track_a_verdict="REVIEW",
        risk_score=0.60,
    )
    _graph.add_edge("ENT-DEMO-002", "ENT-DEMO-003", type="director", weight=0.8)


_seed_graph()

app = FastAPI(title="Graph Engine Service", version="1.2.0")


# ── Request / response models ──────────────────────────────────────────────────

class EntityIngestRequest(BaseModel):
    entity_id: str
    name: str
    country: str = ""
    individual_score: float = 0.0
    ubo_resolution_status: str = "FULL"
    track_a_verdict: str = "NO_MATCH"


class RelationshipRequest(BaseModel):
    entity_a: str
    entity_b: str
    attr_type: str = "shared_attribute"
    weight: float = 0.7


class NetworkAnalysisRequest(BaseModel):
    entity_id: str
    individual_verdict: str = "NO_MATCH"


class NetworkAnalysisResponse(BaseModel):
    entity_id: str
    network_risk_score: float
    escalation_decision: dict
    per_neighbour_attribution: Dict[str, float]
    flagged_neighbour_count: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/ingest-entity")
async def ingest_entity(req: EntityIngestRequest) -> dict:
    with _lock:
        _graph.add_node(
            req.entity_id,
            name=req.name,
            country=req.country,
            track_a_verdict=req.track_a_verdict,
            risk_score=req.individual_score,
            ubo_resolution_status=req.ubo_resolution_status,
        )
    return {"status": "ok", "entity_id": req.entity_id}


@app.post("/add-relationship")
async def add_relationship(req: RelationshipRequest) -> dict:
    with _lock:
        if req.entity_a not in _graph or req.entity_b not in _graph:
            raise HTTPException(
                status_code=404,
                detail=f"One or both entities not found: {req.entity_a}, {req.entity_b}",
            )
        _graph.add_edge(req.entity_a, req.entity_b, type=req.attr_type, weight=req.weight)
    return {"status": "ok", "edge": f"{req.entity_a} -- {req.attr_type} -- {req.entity_b}"}


@app.post("/analyze-network", response_model=NetworkAnalysisResponse)
async def analyze_network(req: NetworkAnalysisRequest) -> NetworkAnalysisResponse:
    with _lock:
        if req.entity_id not in _graph:
            # Unknown entity — no graph data, return zero risk
            return NetworkAnalysisResponse(
                entity_id=req.entity_id,
                network_risk_score=0.0,
                escalation_decision=EscalationEngine().evaluate(
                    network_risk_score=0.0,
                    attribution={},
                    individual_verdict=req.individual_verdict,
                    neighbours=[],
                ).__dict__,
                per_neighbour_attribution={},
                flagged_neighbour_count=0,
            )

        # BFS up to 3 hops; collect flagged neighbours
        neighbours: List[FlaggedNeighbour] = []
        try:
            lengths: Dict[str, int] = nx.single_source_shortest_path_length(
                _graph, req.entity_id, cutoff=3
            )
        except nx.NetworkXError:
            lengths = {}

        for node_id, hop_dist in lengths.items():
            if node_id == req.entity_id or hop_dist == 0:
                continue
            data = _graph.nodes[node_id]
            verdict = data.get("track_a_verdict", "NO_MATCH")
            risk = float(data.get("risk_score", 0.0))
            is_match = verdict == "MATCH"
            is_review = verdict == "REVIEW" and risk >= REVIEW_THRESHOLD
            if not (is_match or is_review):
                continue
            p_f = 1.0 if is_match else risk
            neighbours.append(
                FlaggedNeighbour(
                    neighbour_id=node_id,
                    neighbour_name=data.get("name", node_id),
                    hop_distance=hop_dist,
                    p_f=p_f,
                    track_a_match=is_match,
                )
            )

    scorer = NetworkRiskScorer()
    risk_score, attribution = scorer.compute(neighbours)

    engine = EscalationEngine(review_threshold=REVIEW_THRESHOLD)
    decision = engine.evaluate(
        network_risk_score=risk_score,
        attribution=attribution,
        individual_verdict=req.individual_verdict,
        neighbours=neighbours,
    )

    return NetworkAnalysisResponse(
        entity_id=req.entity_id,
        network_risk_score=risk_score,
        escalation_decision=decision.__dict__,
        per_neighbour_attribution=attribution,
        flagged_neighbour_count=len(neighbours),
    )


@app.get("/graph/nodes")
async def list_nodes() -> dict:
    with _lock:
        return {
            "node_count": _graph.number_of_nodes(),
            "edge_count": _graph.number_of_edges(),
            "nodes": [
                {"id": n, **dict(d)}
                for n, d in _graph.nodes(data=True)
            ],
        }


@app.get("/health")
async def health() -> dict:
    with _lock:
        node_count = _graph.number_of_nodes()
    return {
        "status": "ok",
        "service": "graph-engine",
        "version": "1.2.0",
        "graph_nodes": node_count,
    }
