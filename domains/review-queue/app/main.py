"""review-queue — analyst REVIEW queue service (Section 12.4)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.queue import ReviewQueue
from app.routers import decisions, queue
from app.store import InMemoryQueueItemStore, RedisQueueItemStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = RedisQueueItemStore(settings.redis_url)
    try:
        await store.ping()
    except Exception:
        store = InMemoryQueueItemStore()

    app.state.queue = ReviewQueue(store=store)
    yield


app = FastAPI(title="review-queue", version="1.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(queue.router)
app.include_router(decisions.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "review-queue"}
