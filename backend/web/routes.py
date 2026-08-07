from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from data.upstox_client import UpstoxClient
from data.redis_cache import RedisCache
from data.database import StockDatabase
from web.ws_manager import manager

router = APIRouter()

# Shared references injected by main.py at startup
_upstox_client: UpstoxClient | None = None
_orchestrator = None  # Orchestrator — avoids circular import at module level
_cache: RedisCache | None = None
_db: StockDatabase | None = None


def set_upstox_client(client: UpstoxClient) -> None:
    global _upstox_client
    _upstox_client = client


def set_orchestrator(orchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator


def set_cache(cache: RedisCache) -> None:
    global _cache
    _cache = cache


def set_db(db: StockDatabase) -> None:
    global _db
    _db = db


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "redis":  _cache.is_available if _cache else False,
    }


# ---------------------------------------------------------------------------
# Live market overview — served from Redis → SQLite fallback
# (never calls Upstox directly)
# ---------------------------------------------------------------------------

@router.get("/api/market/overview")
async def market_overview():
    """
    Returns the latest cached market snapshot.

    Priority
    --------
    1. Redis  (hot cache, TTL 90 s) — sub-millisecond read
    2. SQLite (cold cache, last hourly row) — fallback when Redis is down
    3. Empty state + auth hint if neither has data yet

    The Upstox API is never called here — only the ingestor loop calls it.
    """
    # 1. Try Redis first
    if _cache:
        data = await _cache.get_broadcast()
        if data:
            data["_source"] = "redis"
            return data

    # 2. Fall back to SQLite
    if _db:
        snapshot = await _db.get_latest_snapshot()
        if snapshot:
            analysis = await _db.get_latest_analysis()
            return {
                "auth_required": False,
                "indices":  snapshot.get("indices", {}),
                "stocks":   snapshot.get("stocks", {}),
                "nifty":    snapshot.get("indices", {}).get("nifty"),
                "sensex":   snapshot.get("indices", {}).get("sensex"),
                "analysis": analysis or {},
                "summary":  (analysis or {}).get("summary", ""),
                "timestamp": snapshot.get("timestamp"),
                "_source":  "sqlite",
            }

    # 3. No data yet (first boot before first ingestor tick)
    auth_url = _upstox_client.build_auth_url() if _upstox_client else "/auth"
    return {
        "auth_required": not (_upstox_client and _upstox_client.access_token),
        "auth_url":      auth_url,
        "message":       "Waiting for first market data tick. Check back in ~60 seconds.",
        "indices":       {},
        "stocks":        {},
        "_source":       "none",
    }


# ---------------------------------------------------------------------------
# Historical snapshots — for charting and ML data export
# ---------------------------------------------------------------------------

@router.get("/api/market/history")
async def market_history(hours: int = 24):
    """
    Return all hourly SQLite snapshots from the last *hours* hours.

    Query Params
    ------------
    hours : Look-back window in hours (default 24, max 8760 = 1 year)

    Returns
    -------
    JSON list of { timestamp, indices, stocks } dicts ordered ascending.
    """
    if _db is None:
        return {"error": "Database not initialised"}
    hours = min(hours, 8760)
    rows = await _db.get_snapshots_since(hours=hours)
    return {"count": len(rows), "hours": hours, "snapshots": rows}


# ---------------------------------------------------------------------------
# Per-stock deep-dive (historical patterns + fundamentals)
# ---------------------------------------------------------------------------

@router.get("/api/stock/{symbol}")
async def stock_analysis(symbol: str, period: str = "5y"):
    """
    Run a full stock analysis for *symbol*.

    Query Params
    ------------
    period : yfinance period string — "1y", "2y", "5y" (default "5y")

    Returns
    -------
    JSON with keys: symbol, profile (StockProfile), history (HistoricalPattern)

    Results are cached — repeated calls within the staleness window
    (6 h for fundamentals, 24 h for history) return instantly from DB.
    """
    if _orchestrator is None:
        return {"error": "Orchestrator not initialised"}
    symbol = symbol.upper()
    result = await _orchestrator.analyze_stock(symbol=symbol, period=period)
    return result


# ---------------------------------------------------------------------------
# Upstox OAuth flow
# ---------------------------------------------------------------------------

@router.get("/auth")
async def auth_page(request: Request):
    if _upstox_client and _upstox_client.access_token:
        return HTMLResponse("Already authenticated with Upstox. <a href='/'>Go to Dashboard</a>")
    url = _upstox_client.build_auth_url() if _upstox_client else "#"
    return HTMLResponse(f"""
    <html><body style="font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#f8fafc;">
        <div style="text-align:center;">
            <h1 style="color:#1e293b;">StockSense AI</h1>
            <p style="color:#64748b;">Connect your Upstox account to enable real-time data</p>
            <a href="{url}" style="display:inline-block;background:#2563eb;color:white;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;">Authorize Upstox</a>
        </div>
    </body></html>
    """)


@router.get("/callback")
async def callback(request: Request, code: str = None, error: str = None):
    if error:
        return HTMLResponse(f"Authorization failed: {error}")
    if not code:
        return HTMLResponse("No authorization code received.")
    success = await _upstox_client.exchange_code(code)
    if success:
        return RedirectResponse(url="/", status_code=302)
    return HTMLResponse("Failed to authenticate with Upstox. <a href='/auth'>Try again</a>")


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
