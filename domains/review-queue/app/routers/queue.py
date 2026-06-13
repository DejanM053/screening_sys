from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request

from app.models import EnqueueRequest, QueueItem, QueueItemStatus, TransferType

router = APIRouter()


@router.post("/enqueue", response_model=QueueItem)
async def enqueue(req: EnqueueRequest, request: Request) -> QueueItem:
    return await request.app.state.queue.enqueue(req)


@router.get("/queue", response_model=list[QueueItem])
async def list_queue(
    request: Request,
    transfer_type: Optional[TransferType] = None,
    country: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    ubo_resolution_status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    status: QueueItemStatus = QueueItemStatus.PENDING,
) -> list[QueueItem]:
    return await request.app.state.queue.list_items(
        transfer_type=transfer_type,
        country=country,
        min_score=min_score,
        max_score=max_score,
        ubo_resolution_status=ubo_resolution_status,
        assigned_to=assigned_to,
        status=status,
    )
