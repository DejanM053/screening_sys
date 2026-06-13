"""Graph Engine Service — Neo4j UBO traversal + noisy-OR network risk (CC-03)."""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from app.network_risk import (
    EscalationEngine,
    FlaggedNeighbour,
    NetworkRiskScorer,
)
from app import queries

REVIEW_THRESHOLD = 0.50


class Settings(BaseSettings):
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "sanctions_neo4j"

    class Config:
        env_file = ".env"


settings = Settings()
app = FastAPI(title="Graph Engine Service", version="1.2.0")

_driver = None


@app.on_event("startup")
async def startup() -> None:
    global _driver
    _driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    if _driver:
        await _driver.close()


class EntityIngestRequest(BaseModel):
    entity_id: str
    name: str
    country: str
    individual_score: float = 0.0
    ubo_resolution_status: str = "FULL"
    track_a_verdict: str = "NO_MATCH"


class NetworkAnalysisRequest(BaseModel):
    entity_id: str
    individual_verdict: str = "NO_MATCH"


class NetworkAnalysisResponse(BaseModel):
    entity_id: str
    network_risk_score: float
    escalation_decision: dict
    per_neighbour_attribution: Dict[str, float]
    flagged_neighbour_count: int
    cypher_query_used: str = queries.GET_FLAGGED_NEIGHBOURS


@app.post("/ingest-entity")
async def ingest_entity(req: EntityIngestRequest) -> dict:
    if not _driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with _driver.session() as session:
        await session.run(
            queries.MERGE_ENTITY,
            entity_id=req.entity_id,
            name=req.name,
            country=req.country,
            individual_score=req.individual_score,
            ubo_resolution_status=req.ubo_resolution_status,
            track_a_verdict=req.track_a_verdict,
        )
    return {"status": "ok", "entity_id": req.entity_id}


@app.post("/analyze-network", response_model=NetworkAnalysisResponse)
async def analyze_network(req: NetworkAnalysisRequest) -> NetworkAnalysisResponse:
    if not _driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")

    async with _driver.session() as session:
        result = await session.run(
            queries.GET_FLAGGED_NEIGHBOURS,
            entity_id=req.entity_id,
            review_threshold=REVIEW_THRESHOLD,
        )
        records = await result.data()

    neighbours: List[FlaggedNeighbour] = []
    for rec in records:
        p_f = 1.0 if rec["track_a_verdict"] == "MATCH" else rec["risk_score"]
        neighbours.append(FlaggedNeighbour(
            neighbour_id=rec["neighbour_id"],
            neighbour_name=rec["neighbour_name"],
            hop_distance=rec["hop_distance"],
            p_f=float(p_f or 0.0),
            track_a_match=(rec["track_a_verdict"] == "MATCH"),
        ))

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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "graph-engine", "version": "1.2.0"}
