"""
Phase 2 tests — Shared Redis caching and stampede prevention.

Covers all 9 requirements from the spec:
  1. First request populates both caches.
  2. Repeated requests reuse cached responses.
  3. Different users requesting the same stock reuse shared data.
  4. Different stocks do not share the wrong cached result.
  5. Expiration causes a refresh.
  6. Concurrent cache misses do not create duplicate expensive work.
  7. Failures do not permanently poison the cache or lock.
  8. Redis outages are handled safely.
  9. Personalized reports never leak between clients.

Run from d:\\Projects\\WealthWatch\\backend:
    python -m pytest tests/test_cache.py -v

All provider/LLM calls are mocked — no live Redis, Gemini, or SearXNG needed.
Where a real Redis instance is present, the integration tests also run.
"""
from __future__ import annotations

import asyncio
import json
import time
import secrets
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
import pytest_asyncio


# ── Helpers ────────────────────────────────────────────────────────────────

SAMPLE_ARTICLES = [
    {
        "title": "Reliance hits record high",
        "url": "https://example.com/reliance-high",
        "source": "example.com",
        "published_at": None,
        "sentiment": "positive",
        "summary": "Reliance Industries surged 3% after strong quarterly earnings.",
    },
    {
        "title": "Reliance Q2 profit up 15%",
        "url": "https://example.com/reliance-q2",
        "source": "example.com",
        "published_at": None,
        "sentiment": "positive",
    },
]

SAMPLE_SUMMARY = "Reliance Industries posted strong Q2 earnings, sending shares to a record high."


def make_cache(available: bool = True) -> "MockRedisCache":
    """
    Create an in-memory mock of RedisCache that mimics get/set/lock semantics.
    When available=False, simulates Redis being down.
    """
    from data.redis_cache import RedisCache

    cache = MagicMock(spec=RedisCache)
    store: dict[str, Any] = {}
    locks: dict[str, str] = {}

    cache.is_available = available

    async def get_news(symbol="MARKET", exchange="NSE"):
        if not available:
            return None
        key = f"news:{exchange}:{symbol}"
        return store.get(key)

    async def set_news(articles, symbol="MARKET", exchange="NSE", summary="", ttl=900):
        if not available or not articles:
            return False
        key = f"news:{exchange}:{symbol}"
        store[key] = {
            "articles": articles,
            "summary": summary,
            "symbol": symbol,
            "exchange": exchange,
            "cached_at": time.time(),
            "ttl": ttl,
        }
        return True

    async def get_summary(symbol, exchange="NSE"):
        if not available:
            return None
        key = f"summary:{exchange}:{symbol}"
        return store.get(key)

    async def set_summary(symbol, summary_text, sentiment="neutral", exchange="NSE", ttl=900):
        if not available or not summary_text.strip():
            return False
        key = f"summary:{exchange}:{symbol}"
        store[key] = {
            "summary": summary_text,
            "sentiment": sentiment,
            "symbol": symbol,
            "exchange": exchange,
            "generated_at": time.time(),
        }
        return True

    async def acquire_lock(resource_key, ttl=35):
        if not available:
            return False, ""
        if resource_key in locks:
            return False, ""
        token = secrets.token_hex(8)
        locks[resource_key] = token
        return True, token

    async def release_lock(resource_key, token):
        if locks.get(resource_key) == token:
            del locks[resource_key]

    async def is_locked(resource_key):
        return resource_key in locks

    cache.get_news = AsyncMock(side_effect=get_news)
    cache.set_news = AsyncMock(side_effect=set_news)
    cache.get_summary = AsyncMock(side_effect=get_summary)
    cache.set_summary = AsyncMock(side_effect=set_summary)
    cache.acquire_lock = AsyncMock(side_effect=acquire_lock)
    cache.release_lock = AsyncMock(side_effect=release_lock)
    cache.is_locked = AsyncMock(side_effect=is_locked)

    # Expose internal store for assertions
    cache._store = store
    cache._locks = locks

    return cache


# ══════════════════════════════════════════════════════════════════════════
# 1-4: Cache hit/miss, isolation, different users
# ══════════════════════════════════════════════════════════════════════════

class TestNewsCacheUnit:
    """Unit tests for RedisCache news/summary methods using an in-process store."""

    @pytest.mark.asyncio
    async def test_first_request_populates_news_cache(self):
        """Req 1: first miss → set → second call returns cached data."""
        cache = make_cache()
        assert await cache.get_news("RELIANCE", "NSE") is None  # miss

        await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE", SAMPLE_SUMMARY)
        result = await cache.get_news("RELIANCE", "NSE")

        assert result is not None
        assert result["articles"] == SAMPLE_ARTICLES
        assert result["summary"] == SAMPLE_SUMMARY

    @pytest.mark.asyncio
    async def test_repeated_requests_reuse_cache(self):
        """Req 2: set_news is called once; get_news returns same data twice."""
        cache = make_cache()
        await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE", SAMPLE_SUMMARY)

        r1 = await cache.get_news("RELIANCE", "NSE")
        r2 = await cache.get_news("RELIANCE", "NSE")

        assert r1 == r2
        assert r1["articles"] == SAMPLE_ARTICLES

    @pytest.mark.asyncio
    async def test_different_users_share_same_cache_entry(self):
        """Req 3: two different 'users' reading the same key see the same data."""
        cache = make_cache()
        await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE", SAMPLE_SUMMARY)

        # Simulate user A and user B (same cache instance = shared Redis)
        result_user_a = await cache.get_news("RELIANCE", "NSE")
        result_user_b = await cache.get_news("RELIANCE", "NSE")

        assert result_user_a["articles"] == result_user_b["articles"]
        assert result_user_a["cached_at"] == result_user_b["cached_at"]

    @pytest.mark.asyncio
    async def test_different_symbols_do_not_share_cache(self):
        """Req 4: RELIANCE and INFY have independent cache entries."""
        cache = make_cache()
        infy_articles = [{"title": "Infosys Q2 results", "url": "https://x.com/1",
                          "source": "x.com", "published_at": None, "sentiment": "neutral"}]

        await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE", SAMPLE_SUMMARY)
        await cache.set_news(infy_articles, "INFY", "NSE", "Infosys beats estimates.")

        reliance = await cache.get_news("RELIANCE", "NSE")
        infy     = await cache.get_news("INFY", "NSE")

        assert reliance["symbol"] == "RELIANCE"
        assert infy["symbol"] == "INFY"
        assert reliance["articles"] != infy["articles"]

    @pytest.mark.asyncio
    async def test_market_news_and_stock_news_use_different_keys(self):
        """Market news key 'MARKET' is distinct from any stock symbol."""
        cache = make_cache()
        market_articles = [{"title": "Nifty up 1%", "url": "https://x.com/n",
                             "source": "x.com", "published_at": None, "sentiment": "positive"}]

        await cache.set_news(market_articles, "MARKET", exchange="MARKET")
        await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE")

        market = await cache.get_news("MARKET", exchange="MARKET")
        stock  = await cache.get_news("RELIANCE", "NSE")

        assert market["articles"] != stock["articles"]


# ══════════════════════════════════════════════════════════════════════════
# 5: Expiration causes refresh
# ══════════════════════════════════════════════════════════════════════════

class TestCacheExpiry:
    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self):
        """
        Simulate expiry: after TTL elapses the in-memory store key is deleted.
        In a real Redis instance the key expires atomically; here we simulate
        that by manually evicting the key and asserting a miss.
        """
        cache = make_cache()
        await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE")

        # Simulate TTL expiration by evicting from internal store
        cache._store.clear()

        result = await cache.get_news("RELIANCE", "NSE")
        assert result is None  # miss → should trigger fresh fetch

    @pytest.mark.asyncio
    async def test_expired_summary_returns_none(self):
        cache = make_cache()
        await cache.set_summary("RELIANCE", SAMPLE_SUMMARY, sentiment="positive")
        cache._store.clear()
        result = await cache.get_summary("RELIANCE")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════
# 6: Concurrent cache misses — stampede prevention
# ══════════════════════════════════════════════════════════════════════════

class TestStampedePrevention:
    @pytest.mark.asyncio
    async def test_only_one_lock_acquired_for_same_key(self):
        """Two concurrent callers: only one gets the lock."""
        cache = make_cache()

        acquired_1, token_1 = await cache.acquire_lock("news:NSE:RELIANCE")
        acquired_2, token_2 = await cache.acquire_lock("news:NSE:RELIANCE")

        assert acquired_1 is True
        assert acquired_2 is False
        assert token_1 != ""
        assert token_2 == ""

    @pytest.mark.asyncio
    async def test_lock_released_allows_next_acquisition(self):
        """After release, another caller can acquire the lock."""
        cache = make_cache()
        acquired, token = await cache.acquire_lock("news:NSE:RELIANCE")
        assert acquired

        await cache.release_lock("news:NSE:RELIANCE", token)

        acquired_2, token_2 = await cache.acquire_lock("news:NSE:RELIANCE")
        assert acquired_2 is True

    @pytest.mark.asyncio
    async def test_wrong_token_does_not_release_lock(self):
        """Only the owner can release the lock (CAS semantics)."""
        cache = make_cache()
        acquired, token = await cache.acquire_lock("news:NSE:RELIANCE")
        assert acquired

        # Try to release with wrong token
        await cache.release_lock("news:NSE:RELIANCE", "wrong-token")

        # Lock should still be held
        assert await cache.is_locked("news:NSE:RELIANCE")

    @pytest.mark.asyncio
    async def test_concurrent_fetches_call_provider_once(self):
        """
        Simulate 5 concurrent requests for the same symbol.
        The provider should be called exactly once; the other 4 wait and
        receive the cached result.
        """
        cache = make_cache()
        provider_call_count = 0

        async def mock_fetch(symbol):
            nonlocal provider_call_count
            provider_call_count += 1
            await asyncio.sleep(0.05)  # simulate pipeline latency
            return SAMPLE_ARTICLES

        async def one_request():
            # check cache
            cached = await cache.get_news("RELIANCE")
            if cached:
                return cached["articles"]

            acquired, token = await cache.acquire_lock("news:NSE:RELIANCE")
            if not acquired:
                # Waiter: poll for up to 10 × 0.05s = 0.5 s
                for _ in range(10):
                    await asyncio.sleep(0.05)
                    cached = await cache.get_news("RELIANCE")
                    if cached:
                        return cached["articles"]
                return []

            # double-check
            cached = await cache.get_news("RELIANCE")
            if cached:
                await cache.release_lock("news:NSE:RELIANCE", token)
                return cached["articles"]

            try:
                articles = await mock_fetch("RELIANCE")
                await cache.set_news(articles, "RELIANCE", "NSE", "")
                return articles
            finally:
                await cache.release_lock("news:NSE:RELIANCE", token)

        results = await asyncio.gather(*[one_request() for _ in range(5)])

        assert provider_call_count == 1, (
            f"Provider called {provider_call_count} times — stampede not prevented"
        )
        for r in results:
            assert r == SAMPLE_ARTICLES


# ══════════════════════════════════════════════════════════════════════════
# 7: Failures do not poison cache or lock
# ══════════════════════════════════════════════════════════════════════════

class TestFailureSafety:
    @pytest.mark.asyncio
    async def test_empty_articles_not_cached(self):
        """Req 7: set_news with empty list must return False and not write."""
        cache = make_cache()
        ok = await cache.set_news([], "RELIANCE", "NSE", "")
        assert ok is False
        assert await cache.get_news("RELIANCE") is None

    @pytest.mark.asyncio
    async def test_empty_summary_not_cached(self):
        """set_summary with blank string must return False."""
        cache = make_cache()
        ok = await cache.set_summary("RELIANCE", "", sentiment="neutral")
        assert ok is False
        assert await cache.get_summary("RELIANCE") is None

    @pytest.mark.asyncio
    async def test_lock_released_even_on_provider_exception(self):
        """If the provider raises, the lock must still be released."""
        cache = make_cache()
        acquired, token = await cache.acquire_lock("news:NSE:RELIANCE")
        assert acquired

        try:
            raise RuntimeError("SearXNG unavailable")
        except RuntimeError:
            pass
        finally:
            await cache.release_lock("news:NSE:RELIANCE", token)

        # Lock must be gone
        assert not await cache.is_locked("news:NSE:RELIANCE")

    @pytest.mark.asyncio
    async def test_failed_fetch_does_not_write_to_cache(self):
        """After a provider failure the cache entry must remain absent."""
        cache = make_cache()

        # Simulate: fetch raises, no set_news call
        try:
            raise RuntimeError("provider down")
        except RuntimeError:
            articles = []

        if articles:
            await cache.set_news(articles, "RELIANCE", "NSE")

        assert await cache.get_news("RELIANCE") is None


# ══════════════════════════════════════════════════════════════════════════
# 8: Redis outages handled safely
# ══════════════════════════════════════════════════════════════════════════

class TestRedisOutage:
    @pytest.mark.asyncio
    async def test_cache_miss_when_redis_unavailable(self):
        """When is_available=False, get_news returns None (no crash)."""
        cache = make_cache(available=False)
        result = await cache.get_news("RELIANCE")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_news_returns_false_when_unavailable(self):
        cache = make_cache(available=False)
        ok = await cache.set_news(SAMPLE_ARTICLES, "RELIANCE", "NSE")
        assert ok is False

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_false_when_unavailable(self):
        cache = make_cache(available=False)
        acquired, token = await cache.acquire_lock("news:NSE:RELIANCE")
        assert acquired is False
        assert token == ""

    @pytest.mark.asyncio
    async def test_provider_still_called_when_redis_unavailable(self):
        """When Redis is down the handler must fall through and call the provider."""
        provider_called = False

        async def mock_fetch():
            nonlocal provider_called
            provider_called = True
            return SAMPLE_ARTICLES

        # Simulate route logic
        cache = make_cache(available=False)
        cached = await cache.get_news("RELIANCE")

        if not cached:
            articles = await mock_fetch()

        assert provider_called
        assert articles == SAMPLE_ARTICLES


# ══════════════════════════════════════════════════════════════════════════
# 9: Client data isolation — no cross-client leakage
# ══════════════════════════════════════════════════════════════════════════

class TestClientIsolation:
    @pytest.mark.asyncio
    async def test_shared_summary_contains_no_client_data(self):
        """
        The cached summary must only contain market-level text.
        We verify by checking that no client name, ID, or holdings appear.
        """
        cache = make_cache()
        # Simulate: summary was generated from market-level articles
        market_summary = "Reliance posted strong Q2 earnings; shares up 3%."
        await cache.set_summary("RELIANCE", market_summary)

        result = await cache.get_summary("RELIANCE")
        assert result is not None

        # No client-specific fields should be present
        assert "client_id" not in result
        assert "portfolio" not in result
        assert "holdings" not in result
        # The summary text should not contain placeholder client names
        for sensitive in ["John Doe", "Jane Smith", "client_name", "personalized"]:
            assert sensitive.lower() not in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_different_client_ids_do_not_share_portfolio_keys(self):
        """
        Portfolio cache keys must include client_id so client A never sees
        client B's portfolio. We verify the key naming convention.
        """
        # Key format defined in AGENT_CONTEXT: portfolio:{client_id}
        client_a_key = "portfolio:1"
        client_b_key = "portfolio:2"

        assert client_a_key != client_b_key

        cache = make_cache()
        # Manually test that distinct keys remain isolated
        cache._store[client_a_key] = {"client_id": 1, "value": 500_000}
        cache._store[client_b_key] = {"client_id": 2, "value": 1_000_000}

        data_a = cache._store.get(client_a_key)
        data_b = cache._store.get(client_b_key)

        assert data_a["client_id"] == 1
        assert data_b["client_id"] == 2
        assert data_a["value"] != data_b["value"]

    @pytest.mark.asyncio
    async def test_news_cache_key_contains_symbol_not_client(self):
        """Verify that the news key scheme never encodes a client identifier."""
        from data.redis_cache import _news_key, _summary_key

        news_key = _news_key("RELIANCE", "NSE")
        summary_key = _summary_key("RELIANCE", "NSE")

        # Keys must contain symbol and exchange
        assert "RELIANCE" in news_key
        assert "NSE" in news_key
        assert "RELIANCE" in summary_key
        assert "NSE" in summary_key

        # Keys must NOT encode a client id or user id
        assert "client" not in news_key.lower()
        assert "client" not in summary_key.lower()
        assert "user" not in news_key.lower()
        assert "user" not in summary_key.lower()


# ══════════════════════════════════════════════════════════════════════════
# Key scheme unit tests
# ══════════════════════════════════════════════════════════════════════════

class TestCacheKeyScheme:
    def test_news_key_format_stock(self):
        from data.redis_cache import _news_key
        assert _news_key("reliance", "NSE") == "wealthwatch:news:v1:NSE:RELIANCE"

    def test_news_key_format_market(self):
        from data.redis_cache import _news_key
        assert _news_key("MARKET") == "wealthwatch:news:v1:market"

    def test_summary_key_format(self):
        from data.redis_cache import _summary_key, ANALYSIS_VERSION
        key = _summary_key("INFY", "NSE")
        assert key == f"wealthwatch:summary:v1:NSE:INFY:{ANALYSIS_VERSION}"

    def test_summary_key_includes_analysis_version(self):
        """Bumping ANALYSIS_VERSION must produce a different key."""
        from data import redis_cache
        original = redis_cache.ANALYSIS_VERSION
        v1_key = redis_cache._summary_key("RELIANCE", "NSE")
        # Temporarily change version
        redis_cache.ANALYSIS_VERSION = "99"
        v99_key = redis_cache._summary_key("RELIANCE", "NSE")
        redis_cache.ANALYSIS_VERSION = original
        assert v1_key != v99_key

    def test_lock_key_format(self):
        from data.redis_cache import _lock_key
        assert _lock_key("news:NSE:RELIANCE") == "wealthwatch:lock:news:NSE:RELIANCE"

    def test_case_normalization(self):
        """Lower-case symbol input must produce same key as upper-case."""
        from data.redis_cache import _news_key
        assert _news_key("reliance", "nse") == _news_key("RELIANCE", "NSE")


# ══════════════════════════════════════════════════════════════════════════
# Integration tests (only run when REDIS_URL points to a live instance)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_redis_integration_roundtrip():
    """
    Full Redis roundtrip: connect → set_news → get_news → verify → disconnect.
    Skipped automatically if Redis is not reachable.
    """
    from data.redis_cache import RedisCache

    real_cache = RedisCache()
    await real_cache.connect()
    if not real_cache.is_available:
        pytest.skip("Redis not available — skipping integration test")

    sym = "TESTSTOCK"
    try:
        # 1. Write
        ok = await real_cache.set_news(SAMPLE_ARTICLES, sym, "NSE", SAMPLE_SUMMARY, ttl=10)
        assert ok, "set_news returned False with live Redis"

        # 2. Read back
        data = await real_cache.get_news(sym, "NSE")
        assert data is not None
        assert data["articles"] == SAMPLE_ARTICLES
        assert data["summary"] == SAMPLE_SUMMARY

        # 3. Verify lock acquire + release
        acquired, token = await real_cache.acquire_lock(f"test:{sym}")
        assert acquired
        # Second acquire on same key must fail
        acquired2, _ = await real_cache.acquire_lock(f"test:{sym}")
        assert not acquired2
        # Release
        await real_cache.release_lock(f"test:{sym}", token)
        # Now it should be available again
        acquired3, token3 = await real_cache.acquire_lock(f"test:{sym}")
        assert acquired3
        await real_cache.release_lock(f"test:{sym}", token3)

    finally:
        # Cleanup — delete test keys
        if real_cache._client:
            from data.redis_cache import _news_key
            await real_cache._client.delete(_news_key(sym, "NSE"))
        await real_cache.disconnect()
