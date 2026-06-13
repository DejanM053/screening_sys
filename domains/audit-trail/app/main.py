"""audit-trail — write-once audit log, wallet-indexed (Section 11.4)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import export, log
from app.store import InMemoryAuditLogStore, PostgresAuditLogStore

logger = logging.getLogger("audit-trail")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = PostgresAuditLogStore(settings.postgres_url)
    try:
        await store.connect()
        app.state.store = store
    except Exception as exc:  # pragma: no cover - exercised only without Postgres
        logger.warning("Postgres unavailable (%s); falling back to in-memory audit store", exc)
        app.state.store = InMemoryAuditLogStore()
        store = None

    yield

    if store is not None:
        await store.close()


app = FastAPI(title="audit-trail", version="1.2.0", lifespan=lifespan)
app.include_router(log.router)
app.include_router(export.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "audit-trail"}
