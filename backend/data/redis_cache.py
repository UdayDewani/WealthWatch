"""Redis hot cache with generic get/set + market-specific helpers."""
from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from config import REDIS_URL

logger = logging.getLogger("redis_cache")

KEY_SNAPSHOT  = "market:snapshot"
KEY_BROADCAST = "market:broadcast"
_TTL = 90


class RedisCache:
    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        try:
            self._client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await self._client.ping()
            logger.info("Redis connected at %s", REDIS_URL)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — hot cache disabled", exc)
            self._client = None

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # Generic
    async def get(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ex: int = 60) -> bool:
        if not self._client:
            return False
        try:
            await self._client.setex(key, ex, value)
            return True
        except Exception:
            return False

    # Market-specific helpers
    async def set_snapshot(self, data: dict, ttl: int = _TTL) -> bool:
        return await self.set(KEY_SNAPSHOT, json.dumps(data), ttl)

    async def get_snapshot(self) -> Optional[dict]:
        raw = await self.get(KEY_SNAPSHOT)
        return json.loads(raw) if raw else None

    async def set_broadcast(self, data: dict, ttl: int = _TTL) -> bool:
        return await self.set(KEY_BROADCAST, json.dumps(data), ttl)

    async def get_broadcast(self) -> Optional[dict]:
        raw = await self.get(KEY_BROADCAST)
        return json.loads(raw) if raw else None


cache = RedisCache()
