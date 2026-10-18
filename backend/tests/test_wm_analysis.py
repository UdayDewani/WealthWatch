"""
Comprehensive test suite for Phase 3:
Agentic Wealth Manager and Portfolio Intelligence.

Tests cover:
  1. Direct stock exposure scoring & classification (>=5% -> HIGH)
  2. Indirect sector exposure (>=10% -> MODERATE)
  3. No relevant clients (different sector -> LOW / INSUFFICIENT)
  4. Missing portfolio data / no investments (INSUFFICIENT_DATA, no crash)
  5. Multi-manager isolation & IDOR prevention (WM 2 cannot access WM 1's clients)
  6. Invalid stock identifiers (validation & error handling)
  7. Provider failures (SearXNG / Firecrawl / LLM network failure handled gracefully)
  8. Malformed AI output (invalid JSON falls back to deterministic rules)
  9. Cache window verification (shared summary cached, client assessments computed per manager)
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.wealth_manager_graph import (
    score_clients,
    validate_input,
    run_wm_stock_analysis,
    _get_sector,
    SECTOR_MAP,
)


# ── Test Data Helpers ──────────────────────────────────────────────────────

def _make_client(client_id=1, wm_id=1, name="John Doe", risk_profile="moderate"):
    return {
        "id": client_id,
        "wm_id": wm_id,
        "name": name,
        "email": f"client{client_id}@example.com",
        "password_hash": "hash",
        "phone": "9876543210",
        "pan": "ABCDE1234F",
        "risk_profile": risk_profile,
        "joined_date": "2024-01-01",
        "notes": "",
        "created_at": "2024-01-01T00:00:00",
    }


def _make_investment(client_id=1, symbol="RELIANCE", quantity=50, buy_price=2500.0, status="open"):
    return {
        "id": 101,
        "client_id": client_id,
        "asset_type": "stock",
        "asset_name": symbol,
        "symbol": symbol,
        "quantity": quantity,
        "buy_price": buy_price,
        "buy_date": "2024-01-15",
        "sell_price": None,
        "sell_date": None,
        "status": status,
        "notes": "",
        "created_at": "2024-01-15T00:00:00",
    }


def _make_deposit(client_id=1, amount=200000.0):
    return {
        "id": 201,
        "client_id": client_id,
        "amount": amount,
        "note": "Initial deposit",
        "deposited_at": "2024-01-10",
        "created_at": "2024-01-10T00:00:00",
    }


# ── 1. Unit Tests for Scoring & Validation ─────────────────────────────────

def test_symbol_validation_valid():
    """Verify valid symbols are accepted and normalized."""
    for sym in ["RELIANCE", "reliance", "HDFCBANK.NS", "TCS.BO", "M&M", "BAJAJ-AUTO"]:
        state = {
            "symbol": sym,
            "exchange": "NSE",
            "wm_id": 1,
            "db": None,
            "cache": None,
            "news_fetcher": None,
            "validated_symbol": "",
            "error": "",
        }
        res = validate_input(state)
        assert res["error"] == "", f"Should accept valid symbol: {sym}"
        assert res["validated_symbol"] in ("RELIANCE", "HDFCBANK", "TCS", "M&M", "BAJAJ-AUTO")


def test_symbol_validation_invalid():
    """Verify invalid symbols are rejected with error."""
    for bad in ["", "   ", "RELIANCE; DROP TABLE", "../../etc/passwd", "A" * 35]:
        state = {
            "symbol": bad,
            "exchange": "NSE",
            "wm_id": 1,
            "db": None,
            "cache": None,
            "news_fetcher": None,
            "validated_symbol": "",
            "error": "",
        }
        res = validate_input(state)
        assert "Invalid stock symbol" in res["error"]


def test_score_direct_exposure_high():
    """Client holding >=5% allocation in target stock gets HIGH category (>=40 pts)."""
    state = {
        "error": "",
        "validated_symbol": "RELIANCE",
        "market_summary": {"sentiment": "neutral"},
        "client_exposures": [{
            "client_id": 1,
            "display_name": "Alice S.",
            "risk_profile": "moderate",
            "held": True,
            "quantity": 100,
            "buy_price": 2500.0,
            "current_allocation_pct": 25.0,  # 25% > 5%
            "portfolio_value": 1000000.0,
            "total_deposited": 1000000.0,
            "sector_exposure": {"Energy": 25.0},
            "target_sector_pct": 25.0,
            "data_quality": "complete",
            "score": 0,
            "score_breakdown": {},
            "relevance_category": "",
            "explanation": "",
            "key_risks": [],
            "review_priority": "low",
            "evidence": [],
        }],
        "relevant_clients": [],
    }
    result = score_clients(state)
    client = result["client_exposures"][0]
    assert client["relevance_category"] == "HIGH"
    assert client["score"] >= 40
    assert "direct_exposure_high" in client["score_breakdown"]


def test_score_indirect_sector_moderate():
    """Client with >=10% sector exposure (no direct holding) gets MODERATE relevance."""
    state = {
        "error": "",
        "validated_symbol": "RELIANCE",  # Energy sector
        "market_summary": {"sentiment": "neutral"},
        "client_exposures": [{
            "client_id": 2,
            "display_name": "Bob T.",
            "risk_profile": "moderate",
            "held": False,
            "quantity": 0,
            "buy_price": 0.0,
            "current_allocation_pct": 0.0,
            "portfolio_value": 500000.0,
            "total_deposited": 500000.0,
            "sector_exposure": {"Energy": 15.0, "IT": 85.0},
            "target_sector_pct": 15.0,  # >=10% -> +20 pts
            "data_quality": "complete",
            "score": 0,
            "score_breakdown": {},
            "relevance_category": "",
            "explanation": "",
            "key_risks": [],
            "review_priority": "low",
            "evidence": [],
        }],
        "relevant_clients": [],
    }
    result = score_clients(state)
    client = result["client_exposures"][0]
    assert client["relevance_category"] == "MODERATE"
    assert 20 <= client["score"] < 40
    assert client["score_breakdown"].get("sector_high") == 20


def test_score_insufficient_data():
    """Client with 0 investments gets categorized as INSUFFICIENT_DATA."""
    state = {
        "error": "",
        "validated_symbol": "RELIANCE",
        "market_summary": {"sentiment": "neutral"},
        "client_exposures": [{
            "client_id": 3,
            "display_name": "Charlie M.",
            "risk_profile": "conservative",
            "held": False,
            "quantity": 0,
            "buy_price": 0,
            "current_allocation_pct": 0,
            "portfolio_value": 0,
            "total_deposited": 100000.0,
            "sector_exposure": {},
            "target_sector_pct": 0,
            "data_quality": "minimal",
            "score": 0,
            "score_breakdown": {},
            "relevance_category": "",
            "explanation": "",
            "key_risks": [],
            "review_priority": "low",
            "evidence": [],
        }],
        "relevant_clients": [],
    }
    result = score_clients(state)
    client = result["client_exposures"][0]
    assert client["relevance_category"] == "INSUFFICIENT_DATA"


# ── 2. Full Workflow & Security Tests ──────────────────────────────────────

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_clients = AsyncMock(return_value=[_make_client(client_id=1, wm_id=1, name="Alice Doe")])
    db.get_investments = AsyncMock(return_value=[_make_investment(client_id=1, symbol="RELIANCE", quantity=40, buy_price=2500)])
    db.get_deposits = AsyncMock(return_value=[_make_deposit(client_id=1, amount=150000)])
    return db


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.is_available = True
    cache.get_news = AsyncMock(return_value=None)
    cache.get_summary = AsyncMock(return_value=None)
    cache.set_news = AsyncMock(return_value=True)
    cache.set_summary = AsyncMock(return_value=True)
    return cache


@pytest.mark.asyncio
async def test_full_workflow_direct_exposure(mock_db, mock_cache):
    """Direct stock exposure -> client assessed with grounded facts and HIGH relevance."""
    with patch("agents.market_graph._get_llm", return_value=None):
        res = await run_wm_stock_analysis(
            symbol="RELIANCE",
            wm_id=1,
            db=mock_db,
            cache=mock_cache,
            news_fetcher=None,
        )

    assert "client_analysis" in res
    assert res["client_analysis"]["total_clients"] == 1
    assert res["client_analysis"]["high_relevance"] == 1
    c = res["client_analysis"]["clients"][0]
    assert c["display_name"] == "Alice D."
    assert c["relevance_category"] == "HIGH"
    assert c["existing_exposure"]["held"] is True
    assert "disclaimer" in c
    assert "not an investment recommendation" in c["disclaimer"]


@pytest.mark.asyncio
async def test_multi_manager_isolation(mock_cache):
    """Verify WM 1 and WM 2 get strictly isolated client lists (IDOR guard)."""
    db = AsyncMock()
    # Scoped DB returns only clients for that wm_id
    db.get_clients = AsyncMock(side_effect=lambda wm_id: (
        [_make_client(client_id=10, wm_id=1, name="Client One")] if wm_id == 1
        else [_make_client(client_id=20, wm_id=2, name="Client Two")] if wm_id == 2
        else []
    ))
    db.get_investments = AsyncMock(return_value=[_make_investment()])
    db.get_deposits = AsyncMock(return_value=[_make_deposit()])

    with patch("agents.market_graph._get_llm", return_value=None):
        r1 = await run_wm_stock_analysis("RELIANCE", wm_id=1, db=db, cache=mock_cache)
        r2 = await run_wm_stock_analysis("RELIANCE", wm_id=2, db=db, cache=mock_cache)

    c1 = r1["client_analysis"]["clients"]
    c2 = r2["client_analysis"]["clients"]
    assert len(c1) == 1 and c1[0]["client_id"] == 10
    assert len(c2) == 1 and c2[0]["client_id"] == 20
    assert c1[0]["display_name"] == "Client O."
    assert c2[0]["display_name"] == "Client T."


@pytest.mark.asyncio
async def test_no_relevant_clients(mock_db, mock_cache):
    """When a client owns a completely unrelated sector stock, category is LOW."""
    # Client owns TCS (IT), analyzing RELIANCE (Energy)
    mock_db.get_investments = AsyncMock(return_value=[
        _make_investment(symbol="TCS", quantity=10, buy_price=3500.0)
    ])

    with patch("agents.market_graph._get_llm", return_value=None):
        res = await run_wm_stock_analysis("RELIANCE", wm_id=1, db=mock_db, cache=mock_cache)

    assert res["client_analysis"]["high_relevance"] == 0
    assert res["client_analysis"]["low_relevance"] == 1
    c = res["client_analysis"]["clients"][0]
    assert c["relevance_category"] == "LOW"
    assert c["existing_exposure"]["held"] is False


@pytest.mark.asyncio
async def test_missing_portfolio_data_handling(mock_db, mock_cache):
    """Client with zero open investments is marked INSUFFICIENT_DATA without crashing."""
    mock_db.get_investments = AsyncMock(return_value=[])

    with patch("agents.market_graph._get_llm", return_value=None):
        res = await run_wm_stock_analysis("RELIANCE", wm_id=1, db=mock_db, cache=mock_cache)

    assert res["client_analysis"]["insufficient_data"] == 1
    c = res["client_analysis"]["clients"][0]
    assert c["relevance_category"] == "INSUFFICIENT_DATA"
    assert "No active portfolio holdings" in c["explanation"]


@pytest.mark.asyncio
async def test_cache_window_reuse(mock_db):
    """General market summary is fetched from cache once, not refetched per client/run."""
    cached_summary = {
        "summary": "Shared cached analysis for RELIANCE.",
        "sentiment": "bullish",
        "generated_at": 1700000000.0,
        "analysis_version": "1",
    }
    cached_news = {
        "articles": [{
            "title": "Reliance expanding green hydrogen",
            "source": "livemint.com",
            "url": "https://www.livemint.com/market/reliance-news",
            "published_at": "2024-01-20",
            "sentiment": "positive",
        }],
        "summary": "Expansion news",
        "cached_at": 1700000000.0,
    }

    cache = AsyncMock()
    cache.is_available = True
    cache.get_summary = AsyncMock(return_value=cached_summary)
    cache.get_news = AsyncMock(return_value=cached_news)

    fake_fetcher = AsyncMock()
    fake_fetcher.fetch_stock_news = AsyncMock()

    with patch("agents.market_graph._get_llm", return_value=None):
        res = await run_wm_stock_analysis(
            symbol="RELIANCE", wm_id=1, db=mock_db, cache=cache, news_fetcher=fake_fetcher
        )

    # NewsFetcher should NOT have been called because cache hit
    fake_fetcher.fetch_stock_news.assert_not_called()
    assert res["market_summary"]["summary"] == "Shared cached analysis for RELIANCE."
    assert res["market_summary"]["cache_hit"] is True
    assert len(res["news"]) == 1
    assert res["news"][0]["url"] == "https://www.livemint.com/market/reliance-news"


@pytest.mark.asyncio
async def test_provider_failures_graceful_fallback(mock_db, mock_cache):
    """If news fetcher throws an exception, workflow completes gracefully with fallbacks."""
    failing_fetcher = AsyncMock()
    failing_fetcher.fetch_stock_news = AsyncMock(side_effect=RuntimeError("SearXNG unreachable"))

    with patch("agents.market_graph._get_llm", return_value=None):
        res = await run_wm_stock_analysis(
            symbol="INFY", wm_id=1, db=mock_db, cache=mock_cache, news_fetcher=failing_fetcher
        )

    assert "client_analysis" in res
    assert res["symbol"] == "INFY"
    # Fallback market summary exists
    assert "INFY" in res["market_summary"]["summary"]
    assert res["news"] == []


@pytest.mark.asyncio
async def test_malformed_llm_output_fallback(mock_db, mock_cache):
    """If LLM returns unparseable junk/hallucinations, deterministic rules format the explanation."""
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content="INVALID JSON RESPONSE <<<< NOT PARSABLE >>>>"))

    with patch("agents.market_graph._get_llm", return_value=mock_llm):
        res = await run_wm_stock_analysis(
            symbol="RELIANCE", wm_id=1, db=mock_db, cache=mock_cache, news_fetcher=None
        )

    assert "client_analysis" in res
    c = res["client_analysis"]["clients"][0]
    assert c["relevance_category"] == "HIGH"
    # Fell back to rule-based explanation
    assert "holds" in c["explanation"] and "RELIANCE" in c["explanation"]
    assert len(c["key_risks"]) > 0
    assert len(c["evidence"]) > 0
