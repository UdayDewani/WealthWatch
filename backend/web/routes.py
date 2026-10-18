"""
All REST API routes for WealthWatch 2.0.

Sections:
  /api/auth      - WM and client login/register
  /api/wm        - Wealth manager profile
  /api/clients   - Client CRUD
  /api/deposits  - Client deposit tracking
  /api/investments - Investment tracking
  /api/portfolio/{client_id} - Aggregated portfolio view
  /api/market    - Live market data + AI analysis
  /api/markets/assets - Live Upstox Indian indices, equities and ETFs
  /api/client/me - Client self-service (read own data)
  /auth          - Upstox OAuth
  /ws            - WebSocket
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth.jwt_handler import hash_password, verify_password, create_token
from auth.dependencies import require_wm, require_client
from data.database import WealthDatabase
from data.redis_cache import RedisCache

logger = logging.getLogger("routes")

router = APIRouter()

# ── Injected singletons (set by main.py) ─────────────────────────────────
_db:           Optional[WealthDatabase]   = None
_cache:        Optional[RedisCache]       = None
_upstox:       Any = None
_ws_manager:   Any = None
_news_fetcher: Any = None
_langgraph:    Any = None   # run_market_analysis coroutine
_broadcast_fn: Any = None   # broadcast_once coroutine

def set_db(db):           global _db;           _db = db
def set_cache(c):         global _cache;        _cache = c
def set_upstox(u):        global _upstox;       _upstox = u
def set_ws_manager(m):    global _ws_manager;   _ws_manager = m
def set_news_fetcher(n):  global _news_fetcher; _news_fetcher = n
def set_langgraph(fn):    global _langgraph;    _langgraph = fn
def set_broadcast_fn(fn): global _broadcast_fn; _broadcast_fn = fn


# ══════════════════════════════════════════════════════════════════════════
# Pydantic models
# ══════════════════════════════════════════════════════════════════════════

class WMRegister(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ClientCreate(BaseModel):
    name: str
    email: str
    password: str
    phone: str = ""
    pan: str = ""
    risk_profile: str = "moderate"
    joined_date: str = ""
    notes: str = ""

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pan: Optional[str] = None
    risk_profile: Optional[str] = None
    joined_date: Optional[str] = None
    notes: Optional[str] = None

class DepositCreate(BaseModel):
    client_id: int
    amount: float
    note: str = ""
    deposited_at: str = ""

class InvestmentCreate(BaseModel):
    client_id: int
    asset_type: str          # stock | crypto | gold | etf | mutual_fund | forex
    asset_name: str
    symbol: str
    quantity: float
    buy_price: float
    buy_date: str = ""
    notes: str = ""

class CloseInvestment(BaseModel):
    sell_price: float
    sell_date: str = ""


# ══════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════

@router.post("/api/auth/register")
async def register_wm(body: WMRegister):
    """Register a new wealth manager account."""
    existing = await _db.get_wm_by_email(body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    wm_id = await _db.create_wm(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    token = create_token({"sub": str(wm_id), "role": "wm", "email": body.email})
    return {"token": token, "role": "wm", "name": body.name, "email": body.email}


@router.post("/api/auth/wm-login")
async def wm_login(body: LoginRequest):
    """Wealth manager login."""
    wm = await _db.get_wm_by_email(body.email)
    if not wm or not verify_password(body.password, wm["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(wm["id"]), "role": "wm", "email": wm["email"]})
    return {"token": token, "role": "wm", "name": wm["name"], "email": wm["email"]}


@router.post("/api/auth/client-login")
async def client_login(body: LoginRequest):
    """Client portal login."""
    client = await _db.get_client_by_email(body.email)
    if not client or not verify_password(body.password, client["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(client["id"]), "role": "client", "wm_id": client["wm_id"]})
    return {"token": token, "role": "client", "name": client["name"], "email": client["email"]}


# ══════════════════════════════════════════════════════════════════════════
# WM PROFILE
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/wm/me")
async def wm_me(wm=Depends(require_wm)):
    wm_data = await _db.get_wm_by_id(int(wm["sub"]))
    if not wm_data:
        raise HTTPException(404, "WM not found")
    return wm_data


# ══════════════════════════════════════════════════════════════════════════
# CLIENTS
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/clients")
async def list_clients(wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    clients = await _db.get_clients(wm_id)
    # Enrich with deposit totals
    for c in clients:
        deposits = await _db.get_deposits(c["id"])
        c["total_deposited"] = sum(d["amount"] for d in deposits)
        investments = await _db.get_investments(c["id"], status="open")
        c["total_invested"] = sum(i["quantity"] * i["buy_price"] for i in investments)
    return clients


@router.post("/api/clients", status_code=201)
async def create_client(body: ClientCreate, wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    existing = await _db.get_client_by_email(body.email)
    if existing:
        raise HTTPException(400, "Email already exists")
    client_id = await _db.create_client(wm_id, {
        **body.dict(),
        "password_hash": hash_password(body.password),
        "joined_date": body.joined_date or datetime.utcnow().date().isoformat(),
    })
    return {"id": client_id, "message": "Client created"}


@router.put("/api/clients/{client_id}")
async def update_client(client_id: int, body: ClientUpdate, wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    updated = await _db.update_client(client_id, wm_id, body.dict(exclude_none=True))
    if not updated:
        raise HTTPException(404, "Client not found")
    return {"message": "Updated"}


@router.delete("/api/clients/{client_id}")
async def delete_client(client_id: int, wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    await _db.delete_client(client_id, wm_id)
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════
# DEPOSITS
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/clients/{client_id}/deposits")
async def get_deposits(client_id: int, wm=Depends(require_wm)):
    return await _db.get_deposits(client_id)


@router.post("/api/deposits", status_code=201)
async def add_deposit(body: DepositCreate, wm=Depends(require_wm)):
    dep_id = await _db.create_deposit(
        client_id=body.client_id,
        amount=body.amount,
        note=body.note,
        deposited_at=body.deposited_at or datetime.utcnow().date().isoformat(),
    )
    return {"id": dep_id, "message": "Deposit recorded"}


@router.delete("/api/deposits/{deposit_id}")
async def delete_deposit(deposit_id: int, client_id: int, wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    # Verify client belongs to this WM before mutating
    client = await _db.get_client_by_id(client_id, wm_id)
    if not client:
        raise HTTPException(403, "Access denied: client does not belong to this account")
    await _db.delete_deposit(deposit_id, client_id)
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════
# INVESTMENTS
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/clients/{client_id}/investments")
async def get_investments(client_id: int, wm=Depends(require_wm)):
    return await _db.get_investments(client_id)


@router.post("/api/investments", status_code=201)
async def add_investment(body: InvestmentCreate, wm=Depends(require_wm)):
    inv_id = await _db.create_investment(body.client_id, {
        **body.dict(),
        "buy_date": body.buy_date or datetime.utcnow().date().isoformat(),
    })
    return {"id": inv_id, "message": "Investment recorded"}


@router.post("/api/investments/{inv_id}/close")
async def close_investment(inv_id: int, body: CloseInvestment, client_id: int, wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    client = await _db.get_client_by_id(client_id, wm_id)
    if not client:
        raise HTTPException(403, "Access denied: client does not belong to this account")
    await _db.close_investment(
        inv_id, client_id,
        sell_price=body.sell_price,
        sell_date=body.sell_date or datetime.utcnow().date().isoformat(),
    )
    return {"message": "Investment closed"}


@router.delete("/api/investments/{inv_id}")
async def delete_investment(inv_id: int, client_id: int, wm=Depends(require_wm)):
    wm_id = int(wm["sub"])
    client = await _db.get_client_by_id(client_id, wm_id)
    if not client:
        raise HTTPException(403, "Access denied: client does not belong to this account")
    await _db.delete_investment(inv_id, client_id)
    return {"message": "Deleted"}


# ══════════════════════════════════════════════════════════════════════════
# PORTFOLIO SUMMARY
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/clients/{client_id}/portfolio")
async def client_portfolio(client_id: int, wm=Depends(require_wm)):
    """
    Returns a full portfolio summary for a client:
    - total_deposited, total_invested (at cost), available_cash
    - open investments with live P&L (via yfinance fast_info)
    - closed investments summary with realized P&L
    """
    return await _build_portfolio(client_id)


async def _get_live_price(symbol: str) -> Optional[float]:
    """Fetch latest price via yfinance fast_info (best-effort, returns None on failure)."""
    try:
        import yfinance as yf
        import asyncio
        def _fetch():
            t = yf.Ticker(symbol)
            fi = t.fast_info
            return getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None)
        price = await asyncio.to_thread(_fetch)
        return round(float(price), 4) if price else None
    except Exception:
        return None


async def _build_portfolio(client_id: int) -> dict:
    """Shared portfolio builder used by both WM and client portal endpoints."""
    deposits    = await _db.get_deposits(client_id)
    investments = await _db.get_investments(client_id)

    total_deposited = sum(d["amount"] for d in deposits)
    open_inv   = [i for i in investments if i["status"] == "open"]
    closed_inv = [i for i in investments if i["status"] == "closed"]

    total_invested_cost = sum(i["quantity"] * i["buy_price"] for i in open_inv)
    available_cash      = total_deposited - total_invested_cost

    # Fetch all live prices in parallel (was sequential, O(N * 5s) → now ~5s flat)
    import asyncio as _asyncio
    prices = await _asyncio.gather(
        *[_get_live_price(inv["symbol"]) for inv in open_inv]
    )

    enriched_open = []
    for inv, current_price in zip(open_inv, prices):
        cost          = inv["quantity"] * inv["buy_price"]
        current_value = inv["quantity"] * current_price if current_price else cost
        pnl           = current_value - cost
        pnl_pct       = (pnl / cost * 100) if cost else 0
        enriched_open.append({
            **inv,
            "current_price": current_price,
            "current_value": round(current_value, 2),
            "pnl":           round(pnl, 2),
            "pnl_pct":       round(pnl_pct, 2),
        })

    total_current_value = sum(i["current_value"] for i in enriched_open)
    total_pnl           = total_current_value - total_invested_cost

    # Realized P&L from closed positions
    realized_pnl = sum(
        (i["sell_price"] - i["buy_price"]) * i["quantity"]
        for i in closed_inv
        if i.get("sell_price") is not None
    )

    return {
        "total_deposited":    round(total_deposited, 2),
        "total_invested":     round(total_invested_cost, 2),
        "available_cash":     round(available_cash, 2),
        "current_value":      round(total_current_value, 2),
        "unrealized_pnl":     round(total_pnl, 2),
        "realized_pnl":       round(realized_pnl, 2),
        "open_investments":   enriched_open,
        "closed_investments": closed_inv,
        "deposits":           deposits,
    }


# ══════════════════════════════════════════════════════════════════════════
# CLIENT SELF-SERVICE (client portal)
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/client/me")
async def client_me(cl=Depends(require_client)):
    # Client JWT payload: {sub: str(client_id), role: "client", wm_id: int}
    # There is no "email" in the payload — look up by primary key instead.
    client_id = int(cl["sub"])
    client = await _db.get_client_by_id_only(client_id)
    if client:
        client.pop("password_hash", None)
    return client or {}


@router.get("/api/client/me/portfolio")
async def client_own_portfolio(cl=Depends(require_client)):
    client_id = int(cl["sub"])
    return await _build_portfolio(client_id)


@router.post("/api/client/me/request-report", status_code=202)
async def request_report(cl=Depends(require_client)):
    """
    Trigger an async AI portfolio report generation + Gmail delivery.
    Returns immediately with a job_id to poll status against.
    """
    client_id = int(cl["sub"])

    # Prevent spamming: block if a job is already pending/generating
    existing_jobs = await _db.get_report_jobs(client_id, limit=1)
    if existing_jobs and existing_jobs[0]["status"] in ("pending", "generating"):
        return {
            "job_id":  existing_jobs[0]["id"],
            "status":  existing_jobs[0]["status"],
            "message": "A report is already being generated. Please wait.",
        }

    job_id = await _db.create_report_job(client_id)
    import asyncio
    asyncio.create_task(_generate_and_send_report(job_id, client_id))
    return {
        "job_id":  job_id,
        "status":  "pending",
        "message": "Your portfolio report is being generated and will be emailed to you shortly.",
    }


@router.get("/api/client/me/reports")
async def get_my_reports(cl=Depends(require_client)):
    """Return this client's report job history."""
    client_id = int(cl["sub"])
    return await _db.get_report_jobs(client_id, limit=10)


@router.post("/api/clients/{client_id}/request-report", status_code=202)
async def wm_request_report(client_id: int, wm=Depends(require_wm)):
    """
    Wealth Manager triggers a portfolio report for one of their clients.
    Reuses the same background pipeline as the client self-service endpoint.
    """
    wm_id = int(wm["sub"])

    # Verify the client belongs to this WM
    client_row = await _db.get_client_by_id(client_id, wm_id)
    if not client_row:
        raise HTTPException(status_code=404, detail="Client not found")

    # Prevent spamming: block if a job is already pending/generating
    existing_jobs = await _db.get_report_jobs(client_id, limit=1)
    if existing_jobs and existing_jobs[0]["status"] in ("pending", "generating"):
        return {
            "job_id":  existing_jobs[0]["id"],
            "status":  existing_jobs[0]["status"],
            "message": "A report is already being generated. Please wait.",
        }

    import asyncio
    job_id = await _db.create_report_job(client_id)
    asyncio.create_task(_generate_and_send_report(job_id, client_id))
    return {
        "job_id":  job_id,
        "status":  "pending",
        "message": f"Report for {client_row.get('name', 'client')} is being generated and will be emailed shortly.",
    }


async def _generate_and_send_report(job_id: int, client_id: int) -> None:
    """
    Background coroutine — runs the full report pipeline:
    1. Fetch client profile + portfolio
    2. Fetch latest market analysis + news
    3. Run LangGraph report generation (Gemini)
    4. Send HTML email via Gmail SMTP
    5. Update job status in DB
    """
    from agents.report_graph import run_report
    from services.email_service import send_report_email

    try:
        # Mark as generating
        await _db.update_report_job(job_id, "generating")

        # Fetch client profile directly (background task has no WM JWT context)
        client_row: dict = {}
        try:
            import aiosqlite as _aio
            async with _aio.connect("wealthwatch.db") as conn:
                conn.row_factory = _aio.Row
                async with conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)) as cur:
                    row = await cur.fetchone()
                    if row:
                        client_row = dict(row)
        except Exception as exc:
            logger.error("Report job %d: could not fetch client: %s", job_id, exc)

        if not client_row:
            await _db.update_report_job(job_id, "failed", error_msg="Client record not found")
            return

        client_data = {
            "name":         client_row.get("name", "Valued Client"),
            "email":        client_row.get("email", ""),
            "risk_profile": client_row.get("risk_profile", "moderate"),
            "joined_date":  client_row.get("joined_date", ""),
        }

        # Build portfolio
        portfolio = await _build_portfolio(client_id)

        # Latest market analysis from DB
        history = await _db.get_analysis_history(limit=1)
        market_analysis: dict = {}
        if history:
            # history items only have summary/sentiment; fetch full from DB
            try:
                import aiosqlite, json as _json
                async with aiosqlite.connect("wealthwatch.db") as conn:
                    conn.row_factory = aiosqlite.Row
                    async with conn.execute(
                        "SELECT analysis FROM market_analysis ORDER BY id DESC LIMIT 1"
                    ) as cur:
                        row = await cur.fetchone()
                        if row:
                            market_analysis = _json.loads(row["analysis"])
            except Exception:
                pass

        # Latest news — prefer Redis-cached broadcast data to avoid re-running
        # the expensive SearXNG + Firecrawl + Gemini pipeline (up to 28s).
        news: list = []
        if _cache and _cache.is_available:
            try:
                broadcast = await _cache.get_broadcast()
                if broadcast:
                    news = broadcast.get("news", [])
            except Exception:
                pass
        if not news and _news_fetcher:
            try:
                news = await _news_fetcher.fetch_market_news()
            except Exception:
                pass

        # Run report pipeline
        html_body = await run_report(client_data, portfolio, market_analysis, news)

        # Send email
        to_email = client_data["email"]
        if not to_email:
            await _db.update_report_job(job_id, "failed", error_msg="Client has no email address")
            return

        success = await send_report_email(to_email, client_data["name"], html_body)
        now = datetime.utcnow().isoformat()

        if success:
            await _db.update_report_job(job_id, "sent", sent_at=now)
            logger.info("Report job %d: sent to %s", job_id, to_email)
        else:
            await _db.update_report_job(job_id, "failed", error_msg="Email delivery failed — check Gmail credentials")
            logger.error("Report job %d: email delivery failed", job_id)

    except Exception as exc:
        logger.error("Report job %d crashed: %s", job_id, exc, exc_info=True)
        try:
            await _db.update_report_job(job_id, "failed", error_msg=str(exc))
        except Exception:
            pass



# ══════════════════════════════════════════════════════════════════════════
# MARKET DATA
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/health")
async def health():
    return {"status": "ok", "redis": _cache.is_available if _cache else False}


@router.get("/api/market/overview")
async def market_overview():
    """Returns latest market data from Redis → Upstox fallback."""
    if _cache and _cache.is_available:
        data = await _cache.get_broadcast()
        if data:
            return data
    if _upstox:
        try:
            raw = await _upstox.get_live_index_data()
            if raw:
                return {**raw, "auth_required": False}
        except Exception:
            pass
    return {
        "auth_required": not bool(_upstox and getattr(_upstox, "access_token", None)),
        "indices": {}, "stocks": {}, "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/api/markets/assets")
async def multi_asset_data():
    """Return live Markets-page data from Upstox only; never Yahoo Finance."""
    if not _upstox:
        raise HTTPException(
            status_code=503,
            detail="Upstox is not configured. Add the Upstox API credentials and restart the backend.",
        )

    if not getattr(_upstox, "access_token", None):
        return {
            "auth_required": True,
            "source": "upstox",
            "indices": {},
            "stocks": {},
            "etfs": {},
        }

    data = await _upstox.get_live_market_assets()
    if not any(data.values()):
        raise HTTPException(
            status_code=502,
            detail="Upstox did not return any quotes. Reconnect Upstox and try again.",
        )

    return {
        "auth_required": False,
        "source": "upstox",
        "updated_at": datetime.utcnow().isoformat(),
        **data,
    }


@router.get("/api/markets/stocks/{symbol}/news")
async def stock_news(symbol: str, wm=Depends(require_wm)):
    """
    Return an Upstox-only news feed and an AI summary for one NSE stock.
    Upstox articles are fetched live (they are personalised per watchlist).
    The AI summary is shared via Redis (SUMMARY_TTL=15 min) — it describes
    general market conditions and NEVER contains client-specific data.
    """
    from data.redis_cache import SUMMARY_TTL, LOCK_RETRIES, LOCK_POLL_SECONDS
    if not _upstox:
        raise HTTPException(503, "Upstox is not configured")
    try:
        result = await _upstox.get_stock_news(symbol.upper())
    except ValueError as exc:
        raise HTTPException(404, "This stock is not available in the Markets watchlist") from exc
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc

    sym = symbol.upper()
    lock_resource = f"summary:NSE:{sym}"

    # ── Check summary cache first ─────────────────────────────────────────
    if _cache and _cache.is_available:
        cached_sum = await _cache.get_summary(sym)
        if cached_sum:
            result["summary"] = cached_sum["summary"]
            result["summary_cached_at"] = cached_sum.get("generated_at")
            return result

    # ── Acquire lock to prevent parallel LLM calls ────────────────────────
    lock_token = ""
    if _cache and _cache.is_available:
        acquired, lock_token = await _cache.acquire_lock(lock_resource)
        if not acquired:
            logger.info("Summary %s: lock contention — waiting", sym)
            for _ in range(LOCK_RETRIES):
                await asyncio.sleep(LOCK_POLL_SECONDS)
                cached_sum = await _cache.get_summary(sym)
                if cached_sum:
                    result["summary"] = cached_sum["summary"]
                    return result
            logger.warning("Summary %s: lock wait timed out — generating independently", sym)

    # ── Double-check after acquiring lock ─────────────────────────────────
    if lock_token and _cache and _cache.is_available:
        cached_sum = await _cache.get_summary(sym)
        if cached_sum:
            await _cache.release_lock(lock_resource, lock_token)
            result["summary"] = cached_sum["summary"]
            return result

    # ── Generate summary ──────────────────────────────────────────────────
    try:
        from agents.market_graph import summarize_stock_news
        summary_text = await summarize_stock_news(sym, result.get("articles", []))
        result["summary"] = summary_text

        # Cache the generated summary (general market conditions only)
        if summary_text and _cache and _cache.is_available:
            from data.news_fetcher import _sentiment as _detect_sentiment
            sentiment = _detect_sentiment(summary_text)
            await _cache.set_summary(sym, summary_text, sentiment=sentiment, ttl=SUMMARY_TTL)
    finally:
        if lock_token and _cache and _cache.is_available:
            await _cache.release_lock(lock_resource, lock_token)

    return result

@router.post("/api/market/trigger-analysis")
async def trigger_analysis(wm=Depends(require_wm)):
    """
    Manually trigger a LangGraph AI analysis run.
    Fetches latest news + market data, runs Gemini analysis,
    persists to SQLite, and returns the result immediately.
    """
    if not _langgraph:
        raise HTTPException(503, "AI analysis engine not available")

    # Fetch latest market data (from Redis or Upstox)
    market_data: dict = {}
    if _cache and _cache.is_available:
        cached = await _cache.get_broadcast()
        if cached:
            market_data = cached
    if not market_data and _upstox:
        try:
            market_data = await _upstox.get_live_index_data() or {}
        except Exception:
            pass
    if not market_data:
        market_data = {"indices": {}, "stocks": {}, "timestamp": datetime.utcnow().isoformat()}

    # Fetch news
    news: list = []
    if _news_fetcher:
        try:
            news = await _news_fetcher.fetch_market_news()
        except Exception:
            pass

    # Run LangGraph
    analysis = await _langgraph(market_data, news)
    now = datetime.utcnow().isoformat()

    # Persist to DB
    try:
        await _db.save_market_analysis(analysis, now)
    except Exception as e:
        logger.error("Failed to save triggered analysis: %s", e)

    return {"analysis": analysis, "timestamp": now}


@router.get("/api/market/analysis/history")
async def analysis_history(wm=Depends(require_wm)):
    """Return the last 20 market analysis records from SQLite."""
    try:
        return await _db.get_analysis_history(limit=20)
    except Exception as e:
        logger.error("Failed to fetch analysis history: %s", e)
        raise HTTPException(500, "Could not fetch history")


# ══════════════════════════════════════════════════════════════════════════
# NEWS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/news")
async def get_market_news():
    """
    Return latest Indian market news via SearXNG + Firecrawl + LLM.
    Results are cached in Redis for 15 minutes (NEWS_TTL).
    Concurrent requests share one fetch via distributed lock.
    """
    from data.redis_cache import NEWS_TTL, LOCK_RETRIES, LOCK_POLL_SECONDS
    MARKET_KEY = "MARKET"

    # ── 1. Cache check ────────────────────────────────────────────────────
    if _cache and _cache.is_available:
        cached = await _cache.get_news(MARKET_KEY)
        if cached:
            return {
                "articles":  cached.get("articles", []),
                "source":    "cache",
                "available": True,
                "cached_at": cached.get("cached_at"),
            }

    if not _news_fetcher:
        return {"articles": [], "source": "searxng", "available": False}

    # ── 2. Acquire distributed lock (stampede protection) ─────────────────
    lock_token = ""
    if _cache and _cache.is_available:
        acquired, lock_token = await _cache.acquire_lock(f"news:{MARKET_KEY}")
        if not acquired:
            # Another request is already fetching — poll until it finishes
            logger.info("Market news: lock contention — waiting for concurrent fetch")
            for _ in range(LOCK_RETRIES):
                await asyncio.sleep(LOCK_POLL_SECONDS)
                cached = await _cache.get_news(MARKET_KEY)
                if cached:
                    return {
                        "articles":  cached.get("articles", []),
                        "source":    "cache",
                        "available": True,
                        "cached_at": cached.get("cached_at"),
                    }
            # Gave up waiting — fall through to fetch (safe, not ideal)
            logger.warning("Market news: lock wait timed out — fetching independently")

    # ── 3. Double-check after acquiring lock ──────────────────────────────
    if lock_token and _cache and _cache.is_available:
        cached = await _cache.get_news(MARKET_KEY)
        if cached:
            await _cache.release_lock(f"news:{MARKET_KEY}", lock_token)
            return {
                "articles":  cached.get("articles", []),
                "source":    "cache",
                "available": True,
                "cached_at": cached.get("cached_at"),
            }

    # ── 4. Fetch from provider ────────────────────────────────────────────
    articles: list = []
    try:
        articles = await _news_fetcher.fetch_market_news()
    except Exception as e:
        logger.error("Market news error: %s", e)
    finally:
        if lock_token and _cache and _cache.is_available:
            await _cache.release_lock(f"news:{MARKET_KEY}", lock_token)

    # ── 5. Cache only non-empty, successful results ───────────────────────
    if articles and _cache and _cache.is_available:
        summary = articles[0].get("summary", "") if articles else ""
        await _cache.set_news(articles, MARKET_KEY, exchange="MARKET", summary=summary, ttl=NEWS_TTL)

    return {"articles": articles, "source": "searxng", "available": bool(articles)}


@router.get("/api/news/{symbol}")
async def get_stock_news(symbol: str):
    """
    Return stock news for a symbol via SearXNG + Firecrawl + Gemini summary.
    Results are shared across all authenticated users via Redis (NEWS_TTL=15 min).
    Concurrent requests for the same symbol share one fetch via distributed lock.
    Never caches empty results or provider errors.
    """
    from data.redis_cache import NEWS_TTL, SUMMARY_TTL, LOCK_RETRIES, LOCK_POLL_SECONDS
    sym = symbol.upper()
    lock_resource = f"news:NSE:{sym}"

    # ── 1. Cache check ────────────────────────────────────────────────────
    if _cache and _cache.is_available:
        cached = await _cache.get_news(sym)
        if cached:
            return {
                "articles":  cached.get("articles", []),
                "symbol":    sym,
                "summary":   cached.get("summary", ""),
                "available": True,
                "cached_at": cached.get("cached_at"),
                "source":    "cache",
            }

    if not _news_fetcher:
        return {"articles": [], "symbol": sym, "summary": "", "available": False}

    # ── 2. Acquire distributed lock (stampede protection) ─────────────────
    lock_token = ""
    if _cache and _cache.is_available:
        acquired, lock_token = await _cache.acquire_lock(lock_resource)
        if not acquired:
            logger.info("Stock news %s: lock contention — waiting for concurrent fetch", sym)
            for _ in range(LOCK_RETRIES):
                await asyncio.sleep(LOCK_POLL_SECONDS)
                cached = await _cache.get_news(sym)
                if cached:
                    return {
                        "articles":  cached.get("articles", []),
                        "symbol":    sym,
                        "summary":   cached.get("summary", ""),
                        "available": True,
                        "cached_at": cached.get("cached_at"),
                        "source":    "cache",
                    }
            logger.warning("Stock news %s: lock wait timed out — fetching independently", sym)

    # ── 3. Double-check after acquiring lock ──────────────────────────────
    if lock_token and _cache and _cache.is_available:
        cached = await _cache.get_news(sym)
        if cached:
            await _cache.release_lock(lock_resource, lock_token)
            return {
                "articles":  cached.get("articles", []),
                "symbol":    sym,
                "summary":   cached.get("summary", ""),
                "available": True,
                "cached_at": cached.get("cached_at"),
                "source":    "cache",
            }

    # ── 4. Fetch from provider ────────────────────────────────────────────
    articles: list = []
    try:
        articles = await _news_fetcher.fetch_stock_news(sym)
    except Exception as exc:
        logger.error("Stock news error for %s: %s", sym, exc)
    finally:
        if lock_token and _cache and _cache.is_available:
            await _cache.release_lock(lock_resource, lock_token)

    # ── 5. Extract summary (attached to articles[0] by the pipeline) ──────
    summary = ""
    if articles:
        summary = articles[0].pop("summary", "")

    # ── 6. Cache only non-empty, validated results ────────────────────────
    if articles and _cache and _cache.is_available:
        await _cache.set_news(articles, sym, exchange="NSE", summary=summary, ttl=NEWS_TTL)
        # Also populate the summary-only cache so stock_news (Upstox) can reuse it
        if summary:
            from data.news_fetcher import _sentiment as _detect_sentiment
            sentiment = _detect_sentiment(summary)
            await _cache.set_summary(sym, summary, sentiment=sentiment, ttl=SUMMARY_TTL)

    return {
        "articles":  articles,
        "symbol":    sym,
        "summary":   summary,
        "available": bool(articles),
        "source":    "searxng",
    }



# ══════════════════════════════════════════════════════════════════════════
# GOALS
# ══════════════════════════════════════════════════════════════════════════

class GoalCreate(BaseModel):
    title: str
    target: float
    current: float = 0.0
    target_date: str = ""
    note: str = ""


@router.get("/api/clients/{client_id}/goals")
async def get_client_goals(client_id: int, wm=Depends(require_wm)):
    """List all financial goals for a client."""
    return await _db.get_goals(client_id)


@router.post("/api/clients/{client_id}/goals", status_code=201)
async def create_client_goal(client_id: int, body: GoalCreate, wm=Depends(require_wm)):
    """Create a financial goal for a client."""
    goal_id = await _db.create_goal(client_id, body.dict())
    return {"id": goal_id, "message": "Goal created"}


@router.delete("/api/clients/{client_id}/goals/{goal_id}")
async def delete_client_goal(client_id: int, goal_id: int, wm=Depends(require_wm)):
    """Delete a financial goal."""
    await _db.delete_goal(goal_id, client_id)
    return {"message": "Goal deleted"}


@router.patch("/api/clients/{client_id}/goals/{goal_id}")
async def update_goal_progress(client_id: int, goal_id: int, current: float, wm=Depends(require_wm)):
    """Update the current saved amount for a goal."""
    await _db.update_goal_current(goal_id, client_id, current)
    return {"message": "Goal updated"}


@router.get("/api/client/me/goals")
async def my_goals(cl=Depends(require_client)):
    """Client portal: get own goals."""
    client_id = int(cl["sub"])
    return await _db.get_goals(client_id)


@router.post("/api/client/me/goals", status_code=201)
async def add_my_goal(body: GoalCreate, cl=Depends(require_client)):
    """Client portal: add a goal."""
    client_id = int(cl["sub"])
    goal_id = await _db.create_goal(client_id, body.dict())
    return {"id": goal_id, "message": "Goal created"}


@router.delete("/api/client/me/goals/{goal_id}")
async def delete_my_goal(goal_id: int, cl=Depends(require_client)):
    """Client portal: delete a goal."""
    client_id = int(cl["sub"])
    await _db.delete_goal(goal_id, client_id)
    return {"message": "Goal deleted"}


# ══════════════════════════════════════════════════════════════════════════
# WEALTH MANAGER STOCK ANALYSIS (Phase 3)
# ══════════════════════════════════════════════════════════════════════════

@router.get("/api/wm/stock-analysis/{symbol}")
async def wm_stock_analysis(symbol: str, exchange: str = "NSE", wm=Depends(require_wm)):
    """
    Wealth Manager Dashboard: Analyze a stock across all authorized client portfolios.

    Security:
    - wm_id is extracted from the verified JWT (require_wm dependency), never from the request.
    - Client data is retrieved using wm_id-scoped DB queries (IDOR-safe).
    - Returns only client data belonging to this authenticated WM.
    - Shared Redis cache is used for general market intelligence only;
      client-specific assessments are never cached in the shared store.

    Returns:
    - Market summary and sentiment for the selected stock
    - Relevant news articles with source URLs (no invented citations)
    - Per-client relevance scores and grounded explanations
    - Counts by relevance category
    """
    wm_id = int(wm["sub"])

    import re as _re
    sym = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
    if not sym or not _re.match(r'^[A-Z0-9&._-]{1,30}$', sym):
        raise HTTPException(status_code=422, detail=f"Invalid stock symbol: '{symbol}'")

    exchange_clean = exchange.strip().upper()
    if exchange_clean not in ("NSE", "BSE", "CRYPTO", "GLOBAL"):
        exchange_clean = "NSE"

    logger.info(
        "WM stock analysis request: wm_id=%d symbol=%s exchange=%s",
        wm_id, sym, exchange_clean,
    )

    try:
        from agents.wealth_manager_graph import run_wm_stock_analysis
        result = await run_wm_stock_analysis(
            symbol=sym,
            wm_id=wm_id,
            db=_db,
            cache=_cache,
            news_fetcher=_news_fetcher,
            exchange=exchange_clean,
        )
    except Exception as exc:
        logger.error("WM stock analysis endpoint failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis workflow failed")

    if isinstance(result, dict) and "error" in result and not result.get("client_analysis"):
        detail = result["error"]
        if "Invalid stock symbol" in detail:
            raise HTTPException(status_code=422, detail=detail)
        raise HTTPException(status_code=500, detail=detail)

    logger.info(
        "WM stock analysis completed: wm_id=%d symbol=%s clients=%d high=%d moderate=%d",
        wm_id, sym,
        result.get("client_analysis", {}).get("total_clients", 0),
        result.get("client_analysis", {}).get("high_relevance", 0),
        result.get("client_analysis", {}).get("moderate_relevance", 0),
    )

    return result


# ══════════════════════════════════════════════════════════════════════════
# UPSTOX OAuth
# ══════════════════════════════════════════════════════════════════════════

@router.get("/auth")
async def upstox_auth():
    if not _upstox:
        return {"error": "Upstox client not configured"}
    return RedirectResponse(_upstox.build_auth_url())


@router.get("/callback")
async def upstox_callback(code: str):
    if not _upstox:
        raise HTTPException(500, "Upstox not configured")
    await _upstox.exchange_code(code)
    # Immediately trigger a market data broadcast so the Dashboard
    # gets live data right away instead of waiting for the next 60s tick
    if _broadcast_fn:
        import asyncio
        asyncio.create_task(_broadcast_fn())
    return RedirectResponse("http://localhost:3000/manager/dashboard")


# ══════════════════════════════════════════════════════════════════════════
# WebSocket
# ══════════════════════════════════════════════════════════════════════════

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not _ws_manager:
        await websocket.close()
        return
    await _ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_manager.disconnect(websocket)
