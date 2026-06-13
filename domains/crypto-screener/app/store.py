"""Redis-backed key/value + set helpers with in-memory fallback for tests/dev."""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Optional

try:
    import redis.asyncio as redis_asyncio
except ImportError:  # pragma: no cover
    redis_asyncio = None


class KeyValueStore(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None: ...

    @abstractmethod
    async def sadd_with_expiry(self, key: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...


class RedisStore(KeyValueStore):
    def __init__(self, redis_url: str) -> None:
        self._client = redis_asyncio.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> Optional[str]:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        await self._client.set(key, value, ex=ttl_seconds)

    async def sadd_with_expiry(self, key: str, ttl_seconds: int) -> None:
        await self._client.set(key, "1", ex=ttl_seconds)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def ping(self) -> None:
        await self._client.ping()

    async def close(self) -> None:
        await self._client.aclose()


class InMemoryStore(KeyValueStore):
    """Used when Redis is unavailable (tests, local dev)."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, Optional[float]]] = {}

    async def get(self, key: str) -> Optional[str]:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at < time.monotonic():
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._data[key] = (value, expires_at)

    async def sadd_with_expiry(self, key: str, ttl_seconds: int) -> None:
        await self.set(key, "1", ttl_seconds=ttl_seconds)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None


def dump(obj) -> str:
    return json.dumps(obj)


def load(raw: str):
    return json.loads(raw)
