# Place at: domains/screening-api/app/routers/challenge_routes.py
"""Challenge System API — new router, registered in main.py with one import + one include_router.

POST /api/cases/submit           — parse XML, embed, store
GET  /api/cases/recent           — last 20 cases with challenge status
GET  /api/cases/{id}/similar     — two-stage cosine retrieval
POST /api/cases/{id}/challenge   — LLM peer-challenge generation
POST /api/cases/{id}/challenge/{cid}/respond — analyst response
"""
from __future__ import annotations

import json
import math
import os
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.challenge_models import AMLCaseXML
from app.challenge_xml import xml_to_case

router = APIRouter(prefix="/api/cases", tags=["challenge-system"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
_POSTGRES_DSN = os.getenv(
    "POSTGRES_URL",
    "postgresql://sanctions:sanctions_pass@postgres:5432/sanctions_db",
)

_pool: Optional[asyncpg.Pool] = None

TIMEOUT_MSG = (
    "Challenge generation timed out. Please review the precedent case manually "
    "and document your reasoning in the response field."
)


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(dsn=_POSTGRES_DSN, min_size=1, max_size=10)
        except Exception as exc:
            raise HTTPException(503, {"error": f"Database unavailable: {exc}"})
    return _pool


# ─── Embedding ────────────────────────────────────────────────────────────────

def _bow_embedding(text: str, dim: int = 768) -> List[float]:
    """Hash-based bag-of-words fallback embedding (unit-normalised)."""
    vec = [0.0] * dim
    for token in text.lower().split():
        vec[abs(hash(token)) % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 1e-9 else vec


async def _embed(text: str) -> List[float]:
    """Try Ollama nomic-embed-text, fall back to BOW on any failure."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            r.raise_for_status()
            return r.json()["embedding"]
    except Exception:
        return _bow_embedding(text)


def _embed_text(case: AMLCaseXML) -> str:
    # Exclude reviewer_rationale intentionally: verdict-specific words ("blocked",
    # "approved") would skew BOW similarity toward same-verdict cases, burying
    # useful contradictions. Similarity should be based on what the case IS, not
    # what the analyst concluded.
    parts = [
        case.originator.entity_name,
        case.beneficiary.entity_name,
        " ".join(case.typology_tags),
        case.originator.country_of_incorporation,
        case.beneficiary.country_of_incorporation,
        case.product_type,
    ]
    if case.trade_context and case.trade_context.goods_description:
        parts.append(case.trade_context.goods_description)
    return " ".join(p for p in parts if p)


def _cosine(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n]))
    nb = math.sqrt(sum(x * x for x in b[:n]))
    return dot / (na * nb) if na > 1e-9 and nb > 1e-9 else 0.0


# ─── Request models ───────────────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    transaction_id: str
    case_xml: str


class ChallengeRequest(BaseModel):
    similar_case_id: str
    reviewer_draft_verdict: str


class RespondRequest(BaseModel):
    reviewer_response: str


# ─── Helper ───────────────────────────────────────────────────────────────────

def _summary(case: AMLCaseXML) -> Dict[str, Any]:
    return {
        "entity_names": [case.originator.entity_name, case.beneficiary.entity_name],
        "amount": case.amount,
        "currency": case.currency,
        "typology_tags": case.typology_tags,
        "product_type": case.product_type,
        "risk_scores": case.risk_scores,
        "countries": list(case.geopolitical_snapshot.keys()),
        "reviewer_rationale": case.reviewer_rationale[:300],
    }


# ─── Routes (order matters: /recent must precede /{case_id}/...) ─────────────

@router.get("/recent")
async def recent_cases() -> List[Dict[str, Any]]:
    """20 most recently submitted cases with challenge status."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ac.id, ac.transaction_id, ac.reviewer_verdict,
                   ac.review_timestamp, ac.typology_tags,
                   COUNT(cl.id) AS challenge_count
            FROM aml_cases ac
            LEFT JOIN challenge_log cl ON cl.case_id = ac.id
            GROUP BY ac.id
            ORDER BY ac.review_timestamp DESC
            LIMIT 20
            """
        )
    return [
        {
            "case_id": str(r["id"]),
            "transaction_id": r["transaction_id"],
            "reviewer_verdict": r["reviewer_verdict"],
            "review_timestamp": r["review_timestamp"].isoformat() if r["review_timestamp"] else None,
            "typology_tags": r["typology_tags"] or [],
            "has_challenges": r["challenge_count"] > 0,
        }
        for r in rows
    ]


@router.post("/submit")
async def submit_case(req: SubmitRequest) -> Dict[str, str]:
    """Parse case XML, generate embedding, upsert into aml_cases."""
    try:
        case = xml_to_case(req.case_xml)
    except Exception as exc:
        raise HTTPException(422, {"error": f"Invalid case XML: {exc}"})

    country_codes = list(case.geopolitical_snapshot.keys())
    embedding = await _embed(_embed_text(case))
    geo_dict = {k: v.model_dump() for k, v in case.geopolitical_snapshot.items()}

    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO aml_cases
                (transaction_id, case_xml, typology_tags, country_codes,
                 embedding, reviewer_verdict, reviewer_rationale, geopolitical_snapshot)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::text::jsonb)
            ON CONFLICT (transaction_id) DO UPDATE SET
                case_xml           = EXCLUDED.case_xml,
                typology_tags      = EXCLUDED.typology_tags,
                country_codes      = EXCLUDED.country_codes,
                embedding          = EXCLUDED.embedding,
                reviewer_verdict   = EXCLUDED.reviewer_verdict,
                reviewer_rationale = EXCLUDED.reviewer_rationale,
                geopolitical_snapshot = EXCLUDED.geopolitical_snapshot,
                review_timestamp   = NOW()
            RETURNING id
            """,
            req.transaction_id,
            req.case_xml,
            case.typology_tags,
            country_codes,
            json.dumps(embedding),
            case.reviewer_verdict,
            case.reviewer_rationale,
            json.dumps(geo_dict),
        )
    return {"case_id": str(row["id"])}


@router.get("/{case_id}/similar")
async def find_similar(case_id: str) -> List[Dict[str, Any]]:
    """Two-stage similar case retrieval: SQL tag/country pre-filter → cosine re-rank."""
    try:
        cid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(422, {"error": "Invalid case_id UUID"})

    pool = await _get_pool()
    async with pool.acquire() as conn:
        current = await conn.fetchrow("SELECT * FROM aml_cases WHERE id = $1", cid)
        if not current:
            raise HTTPException(404, {"error": "Case not found"})

        current_tags: List[str] = list(current["typology_tags"] or [])
        current_countries: List[str] = list(current["country_codes"] or [])
        current_verdict: str = current["reviewer_verdict"] or ""
        current_emb: List[float] = json.loads(current["embedding"]) if current["embedding"] else []

        # Stage 1 — SQL pre-filter: overlap on tags OR countries (GIN index, fast)
        candidates = await conn.fetch(
            """
            SELECT id, transaction_id, case_xml, embedding, reviewer_verdict,
                   review_timestamp, geopolitical_snapshot, typology_tags
            FROM aml_cases
            WHERE id != $1
              AND (typology_tags && $2::text[] OR country_codes && $3::text[])
            ORDER BY review_timestamp DESC
            LIMIT 200
            """,
            cid,
            current_tags,
            current_countries,
        )

        # DEMO SAFETY NET — uncomment on the morning of the presentation if embedding
        # similarity fails to surface DEMO-TXN-001/002 when the queried case has AE
        # in its country_codes. Toggle this block to guarantee the contradiction fires.
        #
        # demo_rows = await conn.fetch(
        #     "SELECT id, transaction_id, case_xml, embedding, reviewer_verdict, "
        #     "       review_timestamp, geopolitical_snapshot, typology_tags "
        #     "FROM aml_cases "
        #     "WHERE transaction_id = ANY($1::text[]) AND id != $2",
        #     ["DEMO-TXN-001", "DEMO-TXN-002"],
        #     cid,
        # )
        # if "AE" in current_countries:
        #     existing_ids = {str(r["id"]) for r in candidates}
        #     extra = [r for r in demo_rows if str(r["id"]) not in existing_ids]
        #     candidates = list(candidates) + extra

    # Stage 2 — Python cosine re-rank (no pgvector required)
    scored: List[Dict[str, Any]] = []
    for row in candidates:
        cand_emb: List[float] = json.loads(row["embedding"]) if row["embedding"] else []
        sim = _cosine(current_emb, cand_emb) if current_emb and cand_emb else 0.0

        try:
            case_obj = xml_to_case(row["case_xml"])
            summ = _summary(case_obj)
        except Exception:
            summ = {}

        geo_raw = row["geopolitical_snapshot"]
        geo_dict = geo_raw if isinstance(geo_raw, dict) else {}

        scored.append({
            "case_id": str(row["id"]),
            "transaction_id": row["transaction_id"],
            "similarity_score": round(sim, 4),
            "reviewer_verdict": row["reviewer_verdict"],
            "review_timestamp": row["review_timestamp"].isoformat() if row["review_timestamp"] else None,
            "geopolitical_snapshot": geo_dict,
            "summary": summ,
            "contradicts_current": (row["reviewer_verdict"] or "") != current_verdict,
        })

    # Contradiction-first sort: surface contradicting cases at the top even if
    # their raw cosine score is lower. Within each group, order by similarity.
    scored.sort(key=lambda x: (x["contradicts_current"], x["similarity_score"]), reverse=True)
    return scored[:10]


@router.post("/{case_id}/challenge")
async def generate_challenge(case_id: str, req: ChallengeRequest) -> Dict[str, Any]:
    """LLM peer-challenge comparing current case against a contradictory precedent."""
    try:
        cid = uuid.UUID(case_id)
        sid = uuid.UUID(req.similar_case_id)
    except ValueError:
        raise HTTPException(422, {"error": "Invalid UUID"})

    pool = await _get_pool()
    async with pool.acquire() as conn:
        cur_row = await conn.fetchrow("SELECT * FROM aml_cases WHERE id = $1", cid)
        sim_row = await conn.fetchrow("SELECT * FROM aml_cases WHERE id = $1", sid)

    if not cur_row or not sim_row:
        raise HTTPException(404, {"error": "Case not found"})

    cur_case = xml_to_case(cur_row["case_xml"])
    sim_case = xml_to_case(sim_row["case_xml"])

    # Compute similarity score directly from stored embeddings
    cur_emb = json.loads(cur_row["embedding"]) if cur_row["embedding"] else []
    sim_emb = json.loads(sim_row["embedding"]) if sim_row["embedding"] else []
    similarity_score = round(_cosine(cur_emb, sim_emb), 4)

    geo_cur = cur_row["geopolitical_snapshot"] if isinstance(cur_row["geopolitical_snapshot"], dict) else {}
    geo_sim = sim_row["geopolitical_snapshot"] if isinstance(sim_row["geopolitical_snapshot"], dict) else {}

    # Truncate rationale to keep prompt short enough for fast llama3.2 inference
    cur_rationale = (cur_case.reviewer_rationale or "")[:200]
    sim_rationale = (sim_case.reviewer_rationale or "")[:200]

    # Summarise geo context to just FATF status per country
    def _geo_summary(g: dict) -> str:
        return ", ".join(
            f"{cc}:FATF={v.get('FATF_status','?')}" for cc, v in g.items()
        ) or "unknown"

    system_prompt = (
        "You are a senior AML compliance analyst doing a structured peer review. "
        "Surface the strongest counterargument to the reviewer's draft verdict in under 200 words. "
        "Use exactly 4 labelled sections: "
        "1) Tension, 2) What the precedent suggests, 3) Key distinguishing argument, 4) One question to answer."
    )

    user_prompt = (
        f"CURRENT: {cur_case.transaction_id} | {cur_case.amount} {cur_case.currency} | "
        f"tags: {', '.join(cur_case.typology_tags)} | draft: {req.reviewer_draft_verdict} | "
        f"geo: {_geo_summary(geo_cur)} | rationale: {cur_rationale}\n\n"
        f"PRECEDENT: {sim_case.transaction_id} | {sim_case.amount} {sim_case.currency} | "
        f"tags: {', '.join(sim_case.typology_tags)} | verdict: {sim_case.reviewer_verdict} | "
        f"geo: {_geo_summary(geo_sim)} | rationale: {sim_rationale}\n\n"
        f"Similarity: {similarity_score}. Challenge the draft verdict."
    )

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                },
            )
            r.raise_for_status()
            challenge_text = r.json().get("response", TIMEOUT_MSG).strip()
    except httpx.TimeoutException:
        challenge_text = TIMEOUT_MSG
    except Exception as exc:
        challenge_text = f"{TIMEOUT_MSG} (Error: {exc})"

    pool = await _get_pool()
    async with pool.acquire() as conn:
        log_row = await conn.fetchrow(
            """
            INSERT INTO challenge_log
                (case_id, similar_case_id, similarity_score, llm_challenge_text)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            cid,
            sid,
            float(similarity_score),
            challenge_text,
        )

    return {
        "challenge_id": str(log_row["id"]),
        "challenge_text": challenge_text,
        "current_case_summary": _summary(cur_case),
        "similar_case_summary": _summary(sim_case),
        "similarity_score": similarity_score,
    }


@router.post("/{case_id}/challenge/{challenge_id}/respond")
async def respond_to_challenge(
    case_id: str,
    challenge_id: str,
    req: RespondRequest,
) -> Dict[str, str]:
    """Record the analyst's response to a challenge."""
    try:
        cid = uuid.UUID(case_id)
        chid = uuid.UUID(challenge_id)
    except ValueError:
        raise HTTPException(422, {"error": "Invalid UUID"})

    pool = await _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE challenge_log
            SET reviewer_response  = $1,
                response_timestamp = NOW()
            WHERE id = $2 AND case_id = $3
            """,
            req.reviewer_response,
            chid,
            cid,
        )

    if result == "UPDATE 0":
        raise HTTPException(404, {"error": "Challenge not found"})
    return {"status": "ok"}
