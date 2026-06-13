"""list-sync — sanctions list sync service (Section CC-07)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.models import SanctionsList
from app.tasks import SYNC_TASKS

app = FastAPI(title="list-sync", version="1.2.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "list-sync"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/sync/{source}")
async def trigger_sync(source: str) -> dict:
    """Manually trigger a sync for one source (queued via Celery)."""
    try:
        list_name = SanctionsList(source.upper())
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown source '{source}'")

    task = SYNC_TASKS.get(list_name)
    if task is None:
        raise HTTPException(status_code=404, detail=f"No sync task registered for '{source}'")

    async_result = task.delay()
    return {"list_name": list_name.value, "task_id": async_result.id, "status": "queued"}
