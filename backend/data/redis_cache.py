from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from config import REDIS_URL

logger = logging.getLogger("redis_cache")

# ---------------------------------------------------------------------------
# Key names
# ---------------------------------------------------------------------------
KEY_SNAPSHOT = "market:snapshot"   # latest live Upstox data  (TTL 90 s)
KEY_BROADCAST = "market:broadcast" # last full broadcast dict  (TTL 90 s)

# TTL in seconds — slightly longer than the 60 s ingestor interval so the
# key is always present between ticks, but expires quickly after a shutdown.
_TTL = 90


class RedisCache:
    """
    Async Redis wrapper for hot-path market data.

    Design principles
    -----------------
    * All public methods are **safe to call even when Redis is down** — they
      log a warning and return None / False so callers can transparently fall
      back to SQLite.
    * A single ``connect()`` call is made at startup; the client is reused
      for the lifetime of the process.
    * ``is_available`` lets callers skip Redis code paths without raising.
    """

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the Redis connection pool and verify with PING."""
        try:
            self._client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await self._client.ping()
            logger.info("Redis connected at %s", REDIS_URL)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s) — falling back to SQLite only for hot cache.", exc
            )
            self._client = None

    async def disconnect(self) -> None:
        """Gracefully close the Redis connection pool on shutdown."""
        if self._client:
            try:
                await self._client.aclose()
                logger.info("Redis connection closed.")
            except Exception as exc:
                logger.warning("Redis close error: %s", exc)

    @property
    def is_available(self) -> bool:
        """True when Redis is connected and usable."""
        return self._client is not None

    # ------------------------------------------------------------------
    # Market snapshot (raw Upstox data — indices + stocks)
    # ------------------------------------------------------------------

    async def set_snapshot(self, data: dict, ttl: int = _TTL) -> bool:
        """
        Persist the latest Upstox market snapshot to Redis.

        Parameters
        ----------
        data : Raw market dict  (``{"indices": ..., "stocks": ..., "timestamp": ...}``)
        ttl  : Key expiry in seconds (default 90 s)

        Returns
        -------
        True on success, False if Redis is unavailable or the write fails.
        """
        if not self._client:
            return False
        try:
            await self._client.setex(KEY_SNAPSHOT, ttl, json.dumps(data))
            logger.debug("Redis: market:snapshot written (TTL=%ds)", ttl)
            return True
        except Exception as exc:
            logger.warning("Redis set_snapshot failed: %s", exc)
            return False

    async def get_snapshot(self) -> Optional[dict]:
        """
        Retrieve the latest market snapshot from Redis.

        Returns
        -------
        Parsed dict, or None if the key is missing / Redis is unavailable.
        """
        if not self._client:
            return None
        try:
            raw = await self._client.get(KEY_SNAPSHOT)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis get_snapshot failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Broadcast cache (full broadcast payload — indices + stocks + AI)
    # ------------------------------------------------------------------

    async def set_broadcast(self, data: dict, ttl: int = _TTL) -> bool:
        """
        Store the last full broadcast payload (for REST clients that connect
        between WebSocket pushes and want the freshest available data).
        """
        if not self._client:
            return False
        try:
            await self._client.setex(KEY_BROADCAST, ttl, json.dumps(data))
            logger.debug("Redis: market:broadcast written (TTL=%ds)", ttl)
            return True
        except Exception as exc:
            logger.warning("Redis set_broadcast failed: %s", exc)
            return False

    async def get_broadcast(self) -> Optional[dict]:
        """
        Retrieve the last full broadcast payload from Redis.

        Returns
        -------
        Parsed dict, or None if missing / Redis is unavailable.
        """
        if not self._client:
            return None
        try:
            raw = await self._client.get(KEY_BROADCAST)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis get_broadcast failed: %s", exc)
            return None


    # ------------------------------------------------------------------
    # Generic key helpers (used by non-market data e.g. multi-asset)
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """Return the raw string value for *key*, or None."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as exc:
            logger.warning("Redis get(%s) failed: %s", key, exc)
            return None

    async def set(self, key: str, value: str, ex: int = 60) -> bool:
        """Store *value* under *key* with TTL *ex* seconds."""
        if not self._client:
            return False
        try:
            await self._client.setex(key, ex, value)
            return True
        except Exception as exc:
            logger.warning("Redis set(%s) failed: %s", key, exc)
            return False


# ---------------------------------------------------------------------------
# Module-level singleton — imported by main.py and routes.py
# ---------------------------------------------------------------------------
cache = RedisCache()

