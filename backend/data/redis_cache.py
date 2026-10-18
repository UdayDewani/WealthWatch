"""Redis hot cache — market broadcast helpers + shared news/summary caching with stampede protection.

Key scheme (versioned for safe future changes):
  market:snapshot                          — Upstox market snapshot (legacy, kept)
  market:broadcast                         — full broadcast payload (legacy, kept)
  wealthwatch:news:v1:{exchange}:{symbol}  — stock news articles + AI summary
  wealthwatch:news:v1:market               — broad Indian market news
  wealthwatch:summary:v1:{exchange}:{symbol}:{analysis_version}  — AI summary only
  wealthwatch:lock:{key}                   — distributed lock (setnx/expire)

TTLs:
  NEWS_TTL     = 900 s  (15 min) — news doesn't change that fast
  SUMMARY_TTL  = 900 s  (15 min) — same cadence as news
  LOCK_TTL     = 35  s  — must exceed the worst-case pipeline (~28 s) + buffer
  LOCK_POLL_MS = 250 ms — how often waiters retry
  LOCK_RETRIES = 20     — at 250 ms each → max 5 s wait before giving up

Analysis version — bump whenever the prompt/schema changes so stale summaries
are not served after a deploy.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from config import REDIS_URL

logger = logging.getLogger("redis_cache")

# ── Key constants ──────────────────────────────────────────────────────────

KEY_SNAPSHOT  = "market:snapshot"
KEY_BROADCAST = "market:broadcast"

NEWS_TTL          = 900    # 15 minutes
SUMMARY_TTL       = 900    # 15 minutes
LOCK_TTL          = 35     # seconds — must beat the 28 s pipeline timeout
LOCK_POLL_SECONDS = 0.25   # poll interval while waiting for a lock
LOCK_RETRIES      = 20     # 20 × 0.25 s = 5 s max wait

_TTL = 150  # legacy market broadcast TTL (kept for backward compatibility)

# Bump this string whenever the AI prompt or output schema changes so that
# cached summaries from an old schema are never served after a deploy.
ANALYSIS_VERSION = "1"


def _news_key(symbol: str, exchange: str = "NSE") -> str:
    """Canonical key for stock or market news."""
    sym = symbol.upper().strip()
    if sym == "MARKET":
        return "wealthwatch:news:v1:market"
    return f"wealthwatch:news:v1:{exchange.upper()}:{sym}"


def _summary_key(symbol: str, exchange: str = "NSE") -> str:
    """Canonical key for AI market summary."""
    sym = symbol.upper().strip()
    return f"wealthwatch:summary:v1:{exchange.upper()}:{sym}:{ANALYSIS_VERSION}"


def _lock_key(cache_key: str) -> str:
    return f"wealthwatch:lock:{cache_key}"


# ── Cache class ────────────────────────────────────────────────────────────

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

    # ── Generic primitives ─────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as exc:
            logger.warning("Redis GET error [%s]: %s", key, exc)
            return None

    async def set(self, key: str, value: str, ex: int = 60) -> bool:
        if not self._client:
            return False
        try:
            await self._client.setex(key, ex, value)
            return True
        except Exception as exc:
            logger.warning("Redis SET error [%s]: %s", key, exc)
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Redis: corrupt JSON at key %s", key)
            return None

    async def set_json(self, key: str, value: Any, ex: int = 60) -> bool:
        try:
            serialized = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.error("Redis: cannot serialize value for key %s: %s", key, exc)
            return False
        return await self.set(key, serialized, ex)

    # ── Distributed lock ───────────────────────────────────────────────────
    # Uses SET key token NX EX ttl (atomic setnx + expire).
    # Returns (acquired, token) so the caller can release safely.

    async def acquire_lock(
        self,
        resource_key: str,
        ttl: int = LOCK_TTL,
    ) -> tuple[bool, str]:
        """
        Atomically acquire a distributed lock.

        Returns (True, token) on success.
        Returns (False, '') if Redis is unavailable.
        Does NOT wait — callers use wait_for_lock() for that.
        """
        if not self._client:
            return False, ""
        token = secrets.token_hex(16)
        key = _lock_key(resource_key)
        try:
            result = await self._client.set(key, token, nx=True, ex=ttl)
            acquired = result is True
            if acquired:
                logger.debug("Lock acquired: %s (token=%s)", resource_key, token[:8])
            return acquired, token if acquired else ""
        except Exception as exc:
            logger.warning("Redis lock acquire error [%s]: %s", resource_key, exc)
            return False, ""

    async def release_lock(self, resource_key: str, token: str) -> None:
        """
        Release the lock only if we still own it (compare-and-delete via Lua).
        This prevents a timed-out request from deleting another request's lock.
        """
        if not self._client or not token:
            return
        key = _lock_key(resource_key)
        # Lua script: atomic check-and-delete
        lua = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""
        try:
            await self._client.eval(lua, 1, key, token)
            logger.debug("Lock released: %s", resource_key)
        except Exception as exc:
            logger.warning("Redis lock release error [%s]: %s", resource_key, exc)

    async def wait_for_lock(
        self,
        resource_key: str,
        retries: int = LOCK_RETRIES,
        poll: float = LOCK_POLL_SECONDS,
    ) -> tuple[bool, str]:
        """
        Try to acquire the lock, polling up to `retries` times with `poll` second
        intervals. Returns (acquired, token).
        """
        for attempt in range(retries):
            acquired, token = await self.acquire_lock(resource_key)
            if acquired:
                return True, token
            if attempt < retries - 1:
                await asyncio.sleep(poll)
        logger.warning("Lock contention on %s after %d attempts", resource_key, retries)
        return False, ""

    async def is_locked(self, resource_key: str) -> bool:
        """True if a lock is currently held (does not acquire it)."""
        if not self._client:
            return False
        try:
            return await self._client.exists(_lock_key(resource_key)) == 1
        except Exception:
            return False

    # ── News cache ─────────────────────────────────────────────────────────

    async def get_news(
        self, symbol: str = "MARKET", exchange: str = "NSE"
    ) -> Optional[dict]:
        key = _news_key(symbol, exchange)
        data = await self.get_json(key)
        if data is not None:
            logger.info(
                "Cache HIT  news [%s:%s] (%d articles)",
                exchange, symbol, len(data.get("articles", [])),
            )
        else:
            logger.info("Cache MISS news [%s:%s]", exchange, symbol)
        return data

    async def set_news(
        self,
        articles: list[dict],
        symbol: str = "MARKET",
        exchange: str = "NSE",
        summary: str = "",
        ttl: int = NEWS_TTL,
    ) -> bool:
        """
        Store a validated news result. Does NOT store empty article lists —
        a provider failure should never be cached as a success.
        """
        if not articles:
            logger.debug("Skipping news cache set for %s — empty articles", symbol)
            return False
        key = _news_key(symbol, exchange)
        payload = {
            "articles": articles,
            "summary": summary,
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "cached_at": time.time(),
            "ttl": ttl,
        }
        ok = await self.set_json(key, payload, ttl)
        if ok:
            logger.info(
                "Cache SET  news [%s:%s] %d articles TTL=%ds",
                exchange, symbol, len(articles), ttl,
            )
        return ok

    # ── Summary cache ──────────────────────────────────────────────────────

    async def get_summary(
        self, symbol: str, exchange: str = "NSE"
    ) -> Optional[dict]:
        key = _summary_key(symbol, exchange)
        data = await self.get_json(key)
        if data is not None:
            logger.info(
                "Cache HIT  summary [%s:%s] v%s",
                exchange, symbol, ANALYSIS_VERSION,
            )
        else:
            logger.info(
                "Cache MISS summary [%s:%s] v%s",
                exchange, symbol, ANALYSIS_VERSION,
            )
        return data

    async def set_summary(
        self,
        symbol: str,
        summary_text: str,
        sentiment: str = "neutral",
        exchange: str = "NSE",
        ttl: int = SUMMARY_TTL,
    ) -> bool:
        """
        Store a validated summary. Does NOT store empty strings.
        The summary must not contain personalized client information.
        """
        if not summary_text or not summary_text.strip():
            logger.debug("Skipping summary cache set for %s — empty text", symbol)
            return False
        key = _summary_key(symbol, exchange)
        payload = {
            "summary": summary_text.strip(),
            "sentiment": sentiment,
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "analysis_version": ANALYSIS_VERSION,
            "generated_at": time.time(),
        }
        ok = await self.set_json(key, payload, ttl)
        if ok:
            logger.info(
                "Cache SET  summary [%s:%s] v%s TTL=%ds",
                exchange, symbol, ANALYSIS_VERSION, ttl,
            )
        return ok

    # ── Market-specific broadcast helpers (legacy, kept) ──────────────────

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
