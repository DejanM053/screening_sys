"""Key-value backed item store for the review queue, with an in-memory fallback."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class QueueItemStore(ABC):
    @abstractmethod
    async def put(self, key: str, value: str) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> Optional[str]: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def all(self) -> list[str]: ...

    @abstractmethod
    async def ping(self) -> None: ...


class RedisQueueItemStore(QueueItemStore):
    _HASH_KEY = "review_queue:items"

    def __init__(self, redis_url: str):
        import redis.asyncio as redis

        self._client = redis.from_url(redis_url, decode_responses=True)

    async def ping(self) -> None:
        await self._client.ping()

    async def put(self, key: str, value: str) -> None:
        await self._client.hset(self._HASH_KEY, key, value)

    async def get(self, key: str) -> Optional[str]:
        return await self._client.hget(self._HASH_KEY, key)

    async def delete(self, key: str) -> None:
        await self._client.hdel(self._HASH_KEY, key)

    async def all(self) -> list[str]:
        values = await self._client.hgetall(self._HASH_KEY)
        return list(values.values())


class InMemoryQueueItemStore(QueueItemStore):
    def __init__(self):
        self._data: dict[str, str] = {}

    async def ping(self) -> None:
        return None

    async def put(self, key: str, value: str) -> None:
        self._data[key] = value

    async def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def all(self) -> list[str]:
        return list(self._data.values())
