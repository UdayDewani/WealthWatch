from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite

from models.stock_analysis import HistoricalPattern, StockProfile
from models.client import Client, ClientCreate, ClientUpdate

logger = logging.getLogger("database")

# Default DB lives next to the backend root
DB_PATH = Path(__file__).resolve().parent.parent / "stock_data.db"


class StockDatabase:
    """
    Async SQLite store for stock analysis results and market time-series data.

    Tables
    ------
    stock_profiles       — StockProfile records keyed by symbol
    historical_patterns  — HistoricalPattern records keyed by (symbol, period)
    market_snapshots     — Time-series log of hourly Upstox data (for ML training)
    market_analysis      — Time-series log of hourly Gemini LLM outputs

    All rows carry an ``analyzed_at`` / ``captured_at`` ISO-8601 UTC timestamp
    so callers can check staleness before deciding whether to re-run an analysis.
    """

    def __init__(self, db_path: str | Path = DB_PATH) -> None:
        self.db_path = str(db_path)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create tables and indexes if they don't already exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # ----------------------------------------------------------
            # Existing tables (unchanged)
            # ----------------------------------------------------------
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_profiles (
                    symbol      TEXT PRIMARY KEY,
                    analyzed_at TEXT NOT NULL,
                    data_json   TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_patterns (
                    symbol      TEXT NOT NULL,
                    period      TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    data_json   TEXT NOT NULL,
                    PRIMARY KEY (symbol, period)
                )
                """
            )

            # ----------------------------------------------------------
            # market_snapshots — hourly time-series of raw Upstox data.
            # Every row is one ingestor tick persisted to SQLite.
            # Used as cold-storage fallback and ML training dataset.
            # ----------------------------------------------------------
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at  TEXT NOT NULL,
                    indices_json TEXT NOT NULL,
                    stocks_json  TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_snapshots_captured_at
                ON market_snapshots (captured_at)
                """
            )

            # ----------------------------------------------------------
            # market_analysis — hourly time-series of Gemini LLM outputs.
            # Mirrors market_snapshots cadence (written together by ingestor).
            # ----------------------------------------------------------
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS market_analysis (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    analyzed_at   TEXT NOT NULL,
                    analysis_json TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_analyzed_at
                ON market_analysis (analyzed_at)
                """
            )

            # ----------------------------------------------------------
            # clients — wealth manager's customer records
            # ----------------------------------------------------------
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    name         TEXT NOT NULL,
                    email        TEXT NOT NULL,
                    phone        TEXT NOT NULL,
                    pan          TEXT NOT NULL,
                    risk_profile TEXT NOT NULL DEFAULT 'moderate',
                    aum          REAL NOT NULL DEFAULT 0,
                    joined_date  TEXT NOT NULL,
                    notes        TEXT NOT NULL DEFAULT ''
                )
                """
            )

            await db.commit()
        logger.info("Database initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Staleness helper
    # ------------------------------------------------------------------

    async def is_stale(
        self,
        symbol: str,
        table: str,
        max_age_hours: int = 6,
        period: str | None = None,
    ) -> bool:
        """
        Return True if the record is missing or older than *max_age_hours*.

        Parameters
        ----------
        symbol        : Stock symbol (e.g. "HDFCBANK")
        table         : "stock_profiles" or "historical_patterns"
        max_age_hours : Threshold in hours
        period        : Required when table is "historical_patterns"
        """
        if table == "historical_patterns":
            query = "SELECT analyzed_at FROM historical_patterns WHERE symbol = ? AND period = ?"
            params = (symbol, period)
        else:
            query = "SELECT analyzed_at FROM stock_profiles WHERE symbol = ?"
            params = (symbol,)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return True  # no record → treat as stale
                try:
                    analyzed_at = datetime.fromisoformat(row[0])
                    return datetime.utcnow() - analyzed_at > timedelta(hours=max_age_hours)
                except ValueError:
                    return True

    # ------------------------------------------------------------------
    # StockProfile CRUD
    # ------------------------------------------------------------------

    async def get_profile(self, symbol: str) -> Optional[StockProfile]:
        """Retrieve a cached StockProfile or None if not found."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data_json FROM stock_profiles WHERE symbol = ?", (symbol,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    logger.debug("Cache hit — stock_profiles[%s]", symbol)
                    return StockProfile.model_validate_json(row[0])
        return None

    async def save_profile(self, profile: StockProfile) -> None:
        """Upsert a StockProfile with the current UTC timestamp."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO stock_profiles (symbol, analyzed_at, data_json)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    analyzed_at = excluded.analyzed_at,
                    data_json   = excluded.data_json
                """,
                (profile.symbol, profile.analyzed_at, profile.model_dump_json()),
            )
            await db.commit()
        logger.info("Saved profile for %s (analyzed_at=%s)", profile.symbol, profile.analyzed_at)

    # ------------------------------------------------------------------
    # HistoricalPattern CRUD
    # ------------------------------------------------------------------

    async def get_history(self, symbol: str, period: str) -> Optional[HistoricalPattern]:
        """Retrieve a cached HistoricalPattern or None if not found."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT data_json FROM historical_patterns WHERE symbol = ? AND period = ?",
                (symbol, period),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    logger.debug("Cache hit — historical_patterns[%s, %s]", symbol, period)
                    return HistoricalPattern.model_validate_json(row[0])
        return None

    async def save_history(self, pattern: HistoricalPattern) -> None:
        """Upsert a HistoricalPattern with the current UTC timestamp."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO historical_patterns (symbol, period, analyzed_at, data_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, period) DO UPDATE SET
                    analyzed_at = excluded.analyzed_at,
                    data_json   = excluded.data_json
                """,
                (pattern.symbol, pattern.period, pattern.analyzed_at, pattern.model_dump_json()),
            )
            await db.commit()
        logger.info(
            "Saved historical pattern for %s (%s) (analyzed_at=%s)",
            pattern.symbol,
            pattern.period,
            pattern.analyzed_at,
        )

    # ------------------------------------------------------------------
    # Market Snapshot CRUD  (time-series, appended every hour)
    # ------------------------------------------------------------------

    async def save_market_snapshot(
        self,
        indices: dict,
        stocks: dict,
        captured_at: str,
    ) -> None:
        """
        Append one hourly market snapshot row to SQLite.

        Parameters
        ----------
        indices     : Dict of index data (nifty, sensex, niftybank, niftyit)
        stocks      : Dict of stock lists (nifty50, niftybank)
        captured_at : ISO-8601 UTC timestamp string
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO market_snapshots (captured_at, indices_json, stocks_json)
                VALUES (?, ?, ?)
                """,
                (captured_at, json.dumps(indices), json.dumps(stocks)),
            )
            await db.commit()
        logger.info("Saved hourly market snapshot (captured_at=%s)", captured_at)

    async def get_latest_snapshot(self) -> Optional[dict]:
        """
        Return the most recent market snapshot from SQLite as a plain dict.
        Used as cold-storage fallback when Redis is unavailable.
        Returns None if the table is empty.
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT captured_at, indices_json, stocks_json
                FROM market_snapshots
                ORDER BY captured_at DESC
                LIMIT 1
                """
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "timestamp": row[0],
                        "indices":   json.loads(row[1]),
                        "stocks":    json.loads(row[2]),
                        "_source":   "sqlite",
                    }
        return None

    async def get_snapshots_since(self, hours: int = 24) -> list[dict]:
        """
        Return all snapshot rows from the last *hours* hours (ascending order).
        Useful for serving chart data and ML training exports.
        """
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows: list[dict] = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT captured_at, indices_json, stocks_json
                FROM market_snapshots
                WHERE captured_at >= ?
                ORDER BY captured_at ASC
                """,
                (cutoff,),
            ) as cursor:
                async for row in cursor:
                    rows.append({
                        "timestamp": row[0],
                        "indices":   json.loads(row[1]),
                        "stocks":    json.loads(row[2]),
                    })
        return rows

    async def prune_old_snapshots(self, keep_days: int = 90) -> int:
        """
        Delete snapshot rows older than *keep_days*.
        Returns the number of rows deleted.
        """
        cutoff = (datetime.utcnow() - timedelta(days=keep_days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM market_snapshots WHERE captured_at < ?", (cutoff,)
            )
            deleted = cursor.rowcount
            await db.commit()
        if deleted:
            logger.info("Pruned %d snapshot rows older than %d days.", deleted, keep_days)
        return deleted

    # ------------------------------------------------------------------
    # Market Analysis CRUD  (time-series, appended every hour)
    # ------------------------------------------------------------------

    async def save_market_analysis(self, analysis: dict, analyzed_at: str) -> None:
        """
        Append one hourly Gemini LLM analysis result to SQLite.

        Parameters
        ----------
        analysis    : Full dict returned by MarketAnalysisAgent.run()
        analyzed_at : ISO-8601 UTC timestamp string
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO market_analysis (analyzed_at, analysis_json)
                VALUES (?, ?)
                """,
                (analyzed_at, json.dumps(analysis)),
            )
            await db.commit()
        logger.info("Saved hourly market analysis (analyzed_at=%s)", analyzed_at)

    async def get_latest_analysis(self) -> Optional[dict]:
        """
        Return the most recent LLM analysis row from SQLite as a plain dict.
        Used as cold-storage fallback when Redis is unavailable.
        Returns None if the table is empty.
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT analyzed_at, analysis_json
                FROM market_analysis
                ORDER BY analyzed_at DESC
                LIMIT 1
                """
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    result = json.loads(row[1])
                    result["_analyzed_at"] = row[0]
                    return result
        return None

    # ------------------------------------------------------------------
    # Client CRUD  (wealth manager's customers)
    # ------------------------------------------------------------------

    async def create_client(self, data: ClientCreate) -> Client:
        """Insert a new client row and return the full Client with its new id."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO clients (name, email, phone, pan, risk_profile, aum, joined_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (data.name, data.email, data.phone, data.pan,
                 data.risk_profile, data.aum, data.joined_date, data.notes),
            )
            await db.commit()
            new_id = cursor.lastrowid
        logger.info("Created client id=%d name=%s", new_id, data.name)
        return Client(id=new_id, **data.model_dump())

    async def get_all_clients(self) -> list[Client]:
        """Return all client rows ordered by name."""
        clients: list[Client] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM clients ORDER BY name ASC"
            ) as cursor:
                async for row in cursor:
                    clients.append(Client(**dict(row)))
        return clients

    async def get_client(self, client_id: int) -> Optional[Client]:
        """Return a single client by id, or None if not found."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM clients WHERE id = ?", (client_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Client(**dict(row))
        return None

    async def update_client(self, client_id: int, data: ClientUpdate) -> Optional[Client]:
        """
        Apply a partial update to the client row.
        Returns the updated Client, or None if not found.
        """
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            return await self.get_client(client_id)

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [client_id]

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE clients SET {set_clause} WHERE id = ?", values
            )
            await db.commit()
        logger.info("Updated client id=%d fields=%s", client_id, list(updates.keys()))
        return await self.get_client(client_id)

    async def delete_client(self, client_id: int) -> bool:
        """Delete a client by id. Returns True if a row was removed."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM clients WHERE id = ?", (client_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted client id=%d", client_id)
        return deleted
