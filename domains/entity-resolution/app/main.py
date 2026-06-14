"""Entity Resolution Service — fuzzy matching + ES lookup (CC-02)."""
from __future__ import annotations

import json
from typing import List, Optional

import redis.asyncio as aioredis
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from app.fuzzy.matcher import FuzzyMatcher, PhoneticMatcher, MatchCandidate
from app.opensanctions import match_opensanctions
from app.transliteration.normalizer import TransliterationNormalizer


class Settings(BaseSettings):
    elasticsearch_url: str = "http://elasticsearch:9200"
    redis_url: str = "redis://redis:6379"
    cache_ttl_seconds: int = 3600
    opensanctions_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
app = FastAPI(title="Entity Resolution Service", version="1.2.0")

fuzzy = FuzzyMatcher()
phonetic = PhoneticMatcher()
normalizer = TransliterationNormalizer()

_redis: Optional[aioredis.Redis] = None
_es: Optional[AsyncElasticsearch] = None


@app.on_event("startup")
async def startup() -> None:
    global _redis, _es
    _redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        _es = AsyncElasticsearch([settings.elasticsearch_url])
    except Exception:
        _es = None  # no aiohttp or ES not configured — falls back to OpenSanctions API


@app.on_event("shutdown")
async def shutdown() -> None:
    if _redis:
        await _redis.aclose()
    if _es:
        await _es.close()


class MatchRequest(BaseModel):
    name: str
    country: str
    entity_type: str = "business"
    # nullable KYC fields — used when KYC module is activated
    dob: Optional[str] = None
    passport_number: Optional[str] = None
    registration_number: Optional[str] = None


class MatchResponse(BaseModel):
    query_name: str
    normalized_name: str
    top_score: float
    top_match_detail: Optional[str] = None
    corroboration: bool = False
    candidates: List[dict] = Field(default_factory=list)
    ubo_resolution_status: str = "FULL"
    entity_risk_flags_score: float = 0.0
    historical_flag_rate: float = 0.0
    cached: bool = False


@app.post("/match", response_model=MatchResponse)
async def match_entity(req: MatchRequest) -> MatchResponse:
    cache_key = f"er:{req.name}:{req.country}:{req.entity_type}"
    if _redis:
        cached = await _redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return MatchResponse(**data)

    normalized = normalizer.normalize(req.name)
    variants = normalizer.normalize_variants(req.name)

    # Elasticsearch multi-match query
    candidates = []
    if _es:
        try:
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"name": {"query": normalized, "boost": 2}}},
                            {"match": {"aliases": {"query": normalized}}},
                            *[
                                {"match": {"name": {"query": v}}}
                                for v in variants
                            ],
                        ],
                        "filter": [],
                    }
                },
                "size": 10,
            }
            # Apply country filter if provided
            if req.country:
                query["query"]["bool"]["filter"].append(
                    {"term": {"countries": req.country.upper()}}
                )

            result = await _es.search(index="sanctions_entities", body=query)
            for hit in result["hits"]["hits"]:
                src = hit["_source"]
                candidate_name = src.get("name", "")
                composite = fuzzy.score(normalized, normalizer.normalize(candidate_name))
                if phonetic.same_phonetic_family(req.name, candidate_name):
                    composite = min(1.0, composite + 0.05)
                candidates.append({
                    "matched_name": candidate_name,
                    "score": round(composite, 4),
                    "list_source": src.get("list_source", ""),
                    "list_entry_id": hit["_id"],
                    "match_methods_used": ["fuzzy", "phonetic", "es"],
                })
        except Exception:
            pass

    # ── OpenSanctions API fallback when ES returns no candidates ─────────────
    if not candidates:
        candidates = await match_opensanctions(
            name=req.name,
            country=req.country,
            entity_type=req.entity_type,
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_score = candidates[0]["score"] if candidates else 0.0
    top_detail = (
        f"Matched '{candidates[0]['matched_name']}' on {candidates[0]['list_source']} "
        f"at score {top_score:.4f}"
        if candidates
        else None
    )

    # Corroboration: for KYB, check registration number; for KYC (future), check DOB/passport
    corroboration = False
    if req.entity_type == "business" and req.registration_number and candidates:
        top_entry_id = candidates[0].get("list_entry_id", "")
        # Would query ES for registration_number match against top entry
        corroboration = False  # stub — real impl queries ES for ID fields
    elif req.entity_type == "individual" and req.dob and candidates:
        corroboration = False  # stub — activates when KYC module is built

    response_data = {
        "query_name": req.name,
        "normalized_name": normalized,
        "top_score": top_score,
        "top_match_detail": top_detail,
        "corroboration": corroboration,
        "candidates": candidates[:5],
        "ubo_resolution_status": "FULL",
        "entity_risk_flags_score": 0.0,
        "historical_flag_rate": 0.0,
        "cached": False,
    }

    if _redis:
        await _redis.setex(
            cache_key,
            settings.cache_ttl_seconds,
            json.dumps(response_data),
        )

    return MatchResponse(**response_data)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "entity-resolution", "version": "1.2.0"}
