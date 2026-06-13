"""Persistence for explanation records (CC-06) — Redis-backed with in-memory fallback."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

import redis.asyncio as aioredis

from app.models.explanation import ExplanationRecord


class ExplanationStore(ABC):
    @abstractmethod
    async def put(self, payment_id: str, record: ExplanationRecord) -> None:
        ...

    @abstractmethod
    async def get(self, payment_id: str) -> Optional[ExplanationRecord]:
        ...

    @abstractmethod
    async def ping(self) -> bool:
        ...


class RedisExplanationStore(ExplanationStore):
    _KEY_PREFIX = "explanation:"

    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def put(self, payment_id: str, record: ExplanationRecord) -> None:
        await self._redis.set(f"{self._KEY_PREFIX}{payment_id}", record.model_dump_json())

    async def get(self, payment_id: str) -> Optional[ExplanationRecord]:
        raw = await self._redis.get(f"{self._KEY_PREFIX}{payment_id}")
        if raw is None:
            return None
        return ExplanationRecord.model_validate_json(raw)

    async def ping(self) -> bool:
        return bool(await self._redis.ping())


class InMemoryExplanationStore(ExplanationStore):
    def __init__(self) -> None:
        self._data: Dict[str, ExplanationRecord] = {}

    async def put(self, payment_id: str, record: ExplanationRecord) -> None:
        self._data[payment_id] = record

    async def get(self, payment_id: str) -> Optional[ExplanationRecord]:
        return self._data.get(payment_id)

    async def ping(self) -> bool:
        return True
