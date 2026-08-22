from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from agents import Orchestrator
from data import StockDatabase, UpstoxClient, redis_cache, MultiAssetClient
from web.routes import router, set_orchestrator, set_upstox_client, set_cache, set_db, set_asset_client
from web.ws_manager import manager
from config import PORT, SNAPSHOT_INTERVAL_HOURS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Singletons — created once at startup
# ---------------------------------------------------------------------------
db           = StockDatabase()
upstox       = UpstoxClient()
orchestrator = Orchestrator(db=db)
asset_client = MultiAssetClient()

# Inject shared references into the web layer
set_upstox_client(upstox)
set_orchestrator(orchestrator)
set_asset_client(asset_client)

# How often the ingestor loop fires (seconds)
ANALYSIS_INTERVAL = 60


# ---------------------------------------------------------------------------
# Ingestor loop
# ---------------------------------------------------------------------------

async def ingestor_loop() -> None:
    """
    Runs every ANALYSIS_INTERVAL seconds (60 s).

    Responsibilities
    ----------------
    1. Fetch live market data from Upstox (the ONLY place this happens).
    2. Write the raw snapshot to Redis (hot cache, TTL 90 s) — every tick.
    3. Fetch market news + run Gemini AI analysis.
    4. Write the full broadcast payload to Redis (hot cache) — every tick.
    5. Persist raw snapshot + AI analysis to SQLite — once per hour.
    6. Broadcast the full payload to all connected WebSocket clients.

    All consumers (REST routes, LLM agents) read from Redis → SQLite.
    They never call the Upstox API directly.
    """
    await asyncio.sleep(3)  # let the server finish startup

    # Track when we last wrote to SQLite (hourly cadence)
    last_sqlite_write: datetime | None = None

    while True:
        try:
            now = datetime.utcnow()

            # ----------------------------------------------------------------
            # Auth guard
            # ----------------------------------------------------------------
            if not upstox.access_token:
                logger.warning("No Upstox token — broadcasting auth_required.")
                auth_payload = {
                    "auth_required": True,
                    "auth_url":      upstox.build_auth_url(),
                    "message":       "Please authorize Upstox to see live market data.",
                    "timestamp":     now.isoformat(),
                }
                await manager.broadcast(auth_payload)
                await asyncio.sleep(ANALYSIS_INTERVAL)
                continue

            # ----------------------------------------------------------------
            # Step 1 — Fetch live prices from Upstox (single API call)
            # ----------------------------------------------------------------
            upstox_data = await upstox.get_live_index_data()

            if not upstox_data:
                logger.warning("Upstox returned no data — token may be expired.")
                auth_payload = {
                    "auth_required": True,
                    "auth_url":      upstox.build_auth_url(),
                    "message":       "Upstox token expired. Please re-authorize.",
                    "timestamp":     now.isoformat(),
                }
                await manager.broadcast(auth_payload)
                await asyncio.sleep(ANALYSIS_INTERVAL)
                continue

            # ----------------------------------------------------------------
            # Step 2 — Write raw snapshot to Redis (every 60 s)
            # ----------------------------------------------------------------
            snapshot_payload = {
                "indices":   upstox_data.get("indices", {}),
                "stocks":    upstox_data.get("stocks", {}),
                "timestamp": now.isoformat(),
            }
            await redis_cache.set_snapshot(snapshot_payload)

            # ----------------------------------------------------------------
            # Step 3 — Run full AI pipeline via Orchestrator
            # ----------------------------------------------------------------
            broadcast_data = await orchestrator.run_pipeline(upstox_data)

            # ----------------------------------------------------------------
            # Step 4 — Write full broadcast to Redis (every 60 s)
            # ----------------------------------------------------------------
            await redis_cache.set_broadcast(broadcast_data)

            # ----------------------------------------------------------------
            # Step 5 — Persist to SQLite (once per hour)
            # ----------------------------------------------------------------
            hours_since_last = (
                (now - last_sqlite_write).total_seconds() / 3600
                if last_sqlite_write else float("inf")
            )

            if hours_since_last >= SNAPSHOT_INTERVAL_HOURS:
                ts = now.isoformat()
                try:
                    await db.save_market_snapshot(
                        indices=upstox_data.get("indices", {}),
                        stocks=upstox_data.get("stocks", {}),
                        captured_at=ts,
                    )
                    analysis = broadcast_data.get("analysis", {})
                    if analysis:
                        await db.save_market_analysis(analysis=analysis, analyzed_at=ts)
                    last_sqlite_write = now
                    logger.info("Hourly SQLite snapshot written at %s", ts)
                except Exception as db_exc:
                    logger.error("SQLite write failed: %s", db_exc)

            # ----------------------------------------------------------------
            # Step 6 — Broadcast to all WebSocket clients
            # ----------------------------------------------------------------
            await manager.broadcast(broadcast_data)

            logger.info(
                "Tick complete — Nifty=%.2f  Sensex=%.2f  Redis=%s",
                (broadcast_data.get("nifty") or {}).get("price", 0),
                (broadcast_data.get("sensex") or {}).get("price", 0),
                "ok" if redis_cache.is_available else "offline",
            )

        except Exception as exc:
            logger.error("Ingestor loop error: %s", exc, exc_info=True)

        await asyncio.sleep(ANALYSIS_INTERVAL)


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect Redis
    await redis_cache.connect()

    # Inject cache + db into routes
    set_cache(redis_cache)
    set_db(db)

    # Initialise SQLite
    await db.initialize()
    logger.info("Database ready.")

    # Start the background ingestor loop
    task = asyncio.create_task(ingestor_loop())
    logger.info("Ingestor loop started (interval=%ds, SQLite every %dh).",
                ANALYSIS_INTERVAL, SNAPSHOT_INTERVAL_HOURS)

    yield  # app is running

    # Graceful shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await redis_cache.disconnect()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="StockSense AI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)

templates = Jinja2Templates(directory="web/templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
