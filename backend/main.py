"""
WealthWatch 2.0 — Main FastAPI server.
Starts: market ingestor loop + LangGraph analysis pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import PORT, ANALYSIS_INTERVAL, SNAPSHOT_INTERVAL_HOURS
from data.database import WealthDatabase
from data.redis_cache import cache as redis_cache
from agents.market_graph import run_market_analysis
from web.routes import (router, set_db, set_cache,
                        set_upstox, set_ws_manager, set_news_fetcher,
                        set_langgraph, set_broadcast_fn)
from web.ws_manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

# ── Singletons ────────────────────────────────────────────────────────────
db           = WealthDatabase()

# Optional — only if keys are set
_upstox = None
_news_fetcher = None

try:
    from data.upstox_client import UpstoxClient
    _upstox = UpstoxClient()
except Exception as e:
    logger.warning("Upstox client init failed: %s", e)

try:
    from data.news_fetcher import NewsFetcher
    _news_fetcher = NewsFetcher()
except Exception as e:
    logger.warning("News fetcher init failed: %s", e)



# ── Market ingestor loop ──────────────────────────────────────────────────

async def ingestor_loop() -> None:
    await asyncio.sleep(1)
    last_sqlite: datetime | None = None

    while True:
        try:
            now = datetime.utcnow()

            # Fetch news
            news = []
            if _news_fetcher:
                try:
                    news = await _news_fetcher.fetch_market_news()
                except Exception:
                    pass

            # Fetch live Upstox data
            upstox_data = {}
            if _upstox and getattr(_upstox, "access_token", None):
                try:
                    upstox_data = await _upstox.get_live_index_data() or {}
                except Exception as e:
                    logger.warning("Upstox fetch failed: %s", e)

            market_data = {
                "indices": upstox_data.get("indices", {}),
                "stocks":  upstox_data.get("stocks", {}),
                "news":    news,
                "timestamp": now.isoformat(),
            }

            # Run LangGraph analysis
            analysis = await run_market_analysis(market_data, news)

            broadcast = {
                "auth_required": not bool(_upstox and getattr(_upstox, "access_token", None)),
                **market_data,
                "nifty":   market_data["indices"].get("nifty"),
                "sensex":  market_data["indices"].get("sensex"),
                "analysis": analysis,
                "summary":  analysis.get("summary", ""),
            }

            # Redis
            await redis_cache.set_broadcast(broadcast)
            await redis_cache.set_snapshot({"indices": market_data["indices"],
                                             "stocks": market_data["stocks"],
                                             "timestamp": now.isoformat()})

            # SQLite hourly
            hours_since = (now - last_sqlite).total_seconds() / 3600 if last_sqlite else float("inf")
            if hours_since >= SNAPSHOT_INTERVAL_HOURS:
                try:
                    await db.save_market_snapshot(market_data["indices"], market_data["stocks"], now.isoformat())
                    await db.save_market_analysis(analysis, now.isoformat())
                    last_sqlite = now
                except Exception as e:
                    logger.error("SQLite write failed: %s", e)

            # Broadcast WebSocket
            await manager.broadcast(broadcast)

            logger.info("Tick — Nifty=%s  Sensex=%s  Redis=%s",
                        (market_data["indices"].get("nifty") or {}).get("price", "—"),
                        (market_data["indices"].get("sensex") or {}).get("price", "—"),
                        "ok" if redis_cache.is_available else "offline")

        except Exception as e:
            logger.error("Ingestor error: %s", e, exc_info=True)

        await asyncio.sleep(ANALYSIS_INTERVAL)


async def broadcast_once() -> None:
    """Run a single ingestor tick immediately — used after Upstox auth."""
    try:
        now = datetime.utcnow()
        news = []
        if _news_fetcher:
            try:
                news = await _news_fetcher.fetch_market_news()
            except Exception:
                pass

        upstox_data = {}
        if _upstox and getattr(_upstox, "access_token", None):
            try:
                upstox_data = await _upstox.get_live_index_data() or {}
            except Exception as e:
                logger.warning("broadcast_once: Upstox fetch failed: %s", e)

        market_data = {
            "indices": upstox_data.get("indices", {}),
            "stocks":  upstox_data.get("stocks", {}),
            "news":    news,
            "timestamp": now.isoformat(),
        }
        analysis = await run_market_analysis(market_data, news)
        broadcast = {
            "auth_required": False,
            **market_data,
            "nifty":   market_data["indices"].get("nifty"),
            "sensex":  market_data["indices"].get("sensex"),
            "analysis": analysis,
            "summary":  analysis.get("summary", ""),
        }
        await redis_cache.set_broadcast(broadcast)
        await manager.broadcast(broadcast)
        logger.info("broadcast_once complete — Nifty=%s",
                    (market_data["indices"].get("nifty") or {}).get("price", "—"))
    except Exception as e:
        logger.error("broadcast_once failed: %s", e)


# ── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect Redis
    await redis_cache.connect()

    # Init DB
    await db.initialize()

    # Inject into routes
    set_db(db)
    set_cache(redis_cache)
    set_upstox(_upstox)
    set_ws_manager(manager)
    set_news_fetcher(_news_fetcher)
    set_langgraph(run_market_analysis)
    set_broadcast_fn(broadcast_once)

    # Start ingestor
    task = asyncio.create_task(ingestor_loop())
    logger.info("WealthWatch 2.0 started — ingestor interval=%ds", ANALYSIS_INTERVAL)

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await redis_cache.disconnect()
    await db.close()
    logger.info("Shutdown complete.")


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(title="WealthWatch 2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5000", "http://localhost:4040"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        timeout_keep_alive=90,   # news pipeline can take ~25-30s
    )
