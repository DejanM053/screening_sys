"""Screening API — core verdict engine."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import crypto, explanation, fiat
from app.store import InMemoryExplanationStore, RedisExplanationStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = RedisExplanationStore(settings.redis_url)
    try:
        await store.ping()
    except Exception:
        store = InMemoryExplanationStore()
    app.state.explanation_store = store
    yield


app = FastAPI(
    title="Sanctions Screening API",
    version="1.2.0",
    description="KYB-first sanctions screening — two-track verdict engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fiat.router)
app.include_router(crypto.router)
app.include_router(explanation.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "screening-api", "version": "1.2.0"}
