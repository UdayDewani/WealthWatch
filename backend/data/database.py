"""
SQLite database with all tables: wm_users, clients, deposits, investments, market data.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger("database")

DB_PATH = "wealthwatch.db"


class WealthDatabase:
    def __init__(self) -> None:
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._db.commit()
        logger.info("Database initialised at %s", DB_PATH)

    async def _create_tables(self) -> None:
        await self._db.executescript("""
        CREATE TABLE IF NOT EXISTS wm_users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            password_hash TEXT  NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS clients (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            wm_id         INTEGER NOT NULL REFERENCES wm_users(id),
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            phone         TEXT    DEFAULT '',
            pan           TEXT    DEFAULT '',
            risk_profile  TEXT    DEFAULT 'moderate',
            joined_date   TEXT    NOT NULL DEFAULT (date('now')),
            notes         TEXT    DEFAULT '',
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deposits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            amount      REAL    NOT NULL CHECK(amount > 0),
            note        TEXT    DEFAULT '',
            deposited_at TEXT   NOT NULL DEFAULT (date('now')),
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS investments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            asset_type  TEXT    NOT NULL,
            asset_name  TEXT    NOT NULL,
            symbol      TEXT    NOT NULL,
            quantity    REAL    NOT NULL CHECK(quantity > 0),
            buy_price   REAL    NOT NULL CHECK(buy_price > 0),
            buy_date    TEXT    NOT NULL DEFAULT (date('now')),
            sell_price  REAL    DEFAULT NULL,
            sell_date   TEXT    DEFAULT NULL,
            status      TEXT    NOT NULL DEFAULT 'open',
            notes       TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS market_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            indices     TEXT    NOT NULL,
            stocks      TEXT    NOT NULL,
            captured_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market_analysis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis    TEXT    NOT NULL,
            analyzed_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS report_jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            status      TEXT    NOT NULL DEFAULT 'pending',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            sent_at     TEXT    DEFAULT NULL,
            error_msg   TEXT    DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            title       TEXT    NOT NULL,
            target      REAL    NOT NULL CHECK(target > 0),
            current     REAL    NOT NULL DEFAULT 0,
            target_date TEXT    DEFAULT '',
            note        TEXT    DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        """)

    # ── WM Users ─────────────────────────────────────────────────────────

    async def create_wm(self, name: str, email: str, password_hash: str) -> int:
        async with self._db.execute(
            "INSERT INTO wm_users (name, email, password_hash) VALUES (?,?,?)",
            (name, email, password_hash),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid

    async def get_wm_by_email(self, email: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM wm_users WHERE email=?", (email,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_wm_by_id(self, wm_id: int) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT id, name, email, created_at FROM wm_users WHERE id=?", (wm_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    # ── Clients ───────────────────────────────────────────────────────────

    async def create_client(self, wm_id: int, data: dict) -> int:
        async with self._db.execute(
            """INSERT INTO clients (wm_id,name,email,password_hash,phone,pan,risk_profile,joined_date,notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (wm_id, data["name"], data["email"], data["password_hash"],
             data.get("phone",""), data.get("pan",""), data.get("risk_profile","moderate"),
             data.get("joined_date", datetime.utcnow().date().isoformat()), data.get("notes","")),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid

    async def get_clients(self, wm_id: int) -> List[Dict]:
        async with self._db.execute(
            "SELECT id,name,email,phone,pan,risk_profile,joined_date,notes FROM clients WHERE wm_id=? ORDER BY name",
            (wm_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_client_by_id(self, client_id: int, wm_id: int) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM clients WHERE id=? AND wm_id=?", (client_id, wm_id)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_client_by_email(self, email: str) -> Optional[Dict]:
        async with self._db.execute(
            "SELECT * FROM clients WHERE email=?", (email,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_client(self, client_id: int, wm_id: int, data: dict) -> bool:
        fields = ["name","email","phone","pan","risk_profile","joined_date","notes"]
        updates = {k: data[k] for k in fields if k in data}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [client_id, wm_id]
        await self._db.execute(
            f"UPDATE clients SET {set_clause} WHERE id=? AND wm_id=?", values
        )
        await self._db.commit()
        return True

    async def delete_client(self, client_id: int, wm_id: int) -> bool:
        await self._db.execute(
            "DELETE FROM clients WHERE id=? AND wm_id=?", (client_id, wm_id)
        )
        await self._db.commit()
        return True

    # ── Deposits ─────────────────────────────────────────────────────────

    async def create_deposit(self, client_id: int, amount: float, note: str, deposited_at: str) -> int:
        async with self._db.execute(
            "INSERT INTO deposits (client_id, amount, note, deposited_at) VALUES (?,?,?,?)",
            (client_id, amount, note, deposited_at),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid

    async def get_deposits(self, client_id: int) -> List[Dict]:
        async with self._db.execute(
            "SELECT * FROM deposits WHERE client_id=? ORDER BY deposited_at DESC",
            (client_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def delete_deposit(self, deposit_id: int, client_id: int) -> None:
        await self._db.execute(
            "DELETE FROM deposits WHERE id=? AND client_id=?", (deposit_id, client_id)
        )
        await self._db.commit()

    # ── Investments ───────────────────────────────────────────────────────

    async def create_investment(self, client_id: int, data: dict) -> int:
        async with self._db.execute(
            """INSERT INTO investments (client_id,asset_type,asset_name,symbol,quantity,buy_price,buy_date,notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (client_id, data["asset_type"], data["asset_name"], data["symbol"],
             data["quantity"], data["buy_price"], data["buy_date"], data.get("notes","")),
        ) as cur:
            await self._db.commit()
            return cur.lastrowid

    async def get_investments(self, client_id: int, status: str = None) -> List[Dict]:
        if status:
            async with self._db.execute(
                "SELECT * FROM investments WHERE client_id=? AND status=? ORDER BY buy_date DESC",
                (client_id, status)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]
        async with self._db.execute(
            "SELECT * FROM investments WHERE client_id=? ORDER BY buy_date DESC",
            (client_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def close_investment(self, inv_id: int, client_id: int, sell_price: float, sell_date: str) -> None:
        await self._db.execute(
            "UPDATE investments SET sell_price=?, sell_date=?, status='closed' WHERE id=? AND client_id=?",
            (sell_price, sell_date, inv_id, client_id)
        )
        await self._db.commit()

    async def delete_investment(self, inv_id: int, client_id: int) -> None:
        await self._db.execute(
            "DELETE FROM investments WHERE id=? AND client_id=?", (inv_id, client_id)
        )
        await self._db.commit()

    # ── Market Data ───────────────────────────────────────────────────────

    async def save_market_snapshot(self, indices: dict, stocks: dict, captured_at: str) -> None:
        await self._db.execute(
            "INSERT INTO market_snapshots (indices,stocks,captured_at) VALUES (?,?,?)",
            (json.dumps(indices), json.dumps(stocks), captured_at)
        )
        await self._db.commit()

    async def save_market_analysis(self, analysis: dict, analyzed_at: str) -> None:
        await self._db.execute(
            "INSERT INTO market_analysis (analysis,analyzed_at) VALUES (?,?)",
            (json.dumps(analysis), analyzed_at)
        )
        await self._db.commit()

    # ── Report Jobs ───────────────────────────────────────────────────────

    async def create_report_job(self, client_id: int) -> int:
        """Insert a new pending report job and return its ID."""
        async with self._db.execute(
            "INSERT INTO report_jobs (client_id, status) VALUES (?, 'pending')",
            (client_id,)
        ) as cur:
            await self._db.commit()
            return cur.lastrowid

    async def update_report_job(
        self, job_id: int, status: str,
        error_msg: str = "", sent_at: str = ""
    ) -> None:
        """Update job status, optionally recording sent_at and error_msg."""
        if sent_at:
            await self._db.execute(
                "UPDATE report_jobs SET status=?, sent_at=?, error_msg=? WHERE id=?",
                (status, sent_at, error_msg, job_id)
            )
        else:
            await self._db.execute(
                "UPDATE report_jobs SET status=?, error_msg=? WHERE id=?",
                (status, error_msg, job_id)
            )
        await self._db.commit()

    async def get_report_jobs(self, client_id: int, limit: int = 10) -> List[Dict]:
        """Return the last `limit` report jobs for a client, newest first."""
        async with self._db.execute(
            "SELECT * FROM report_jobs WHERE client_id=? ORDER BY id DESC LIMIT ?",
            (client_id, limit)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ── Analysis History ──────────────────────────────────────────────────

    async def get_analysis_history(self, limit: int = 20) -> List[Dict]:
        """Return the last `limit` market analysis records, newest first."""
        async with self._db.execute(
            "SELECT id, analysis, analyzed_at FROM market_analysis ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cur:
            rows = await cur.fetchall()
        result = []
        for row in rows:
            try:
                data = json.loads(row["analysis"])
            except Exception:
                data = {}
            result.append({
                "id":        row["id"],
                "timestamp": row["analyzed_at"],
                "sentiment": data.get("sentiment", "neutral"),
                "summary":   data.get("summary", ""),
            })
        return result

    # ── Goals ─────────────────────────────────────────────────────────────

    async def get_goals(self, client_id: int) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM goals WHERE client_id=? ORDER BY created_at DESC", (client_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def create_goal(self, client_id: int, data: dict) -> int:
        cur = await self._db.execute(
            """INSERT INTO goals (client_id, title, target, current, target_date, note)
               VALUES (?,?,?,?,?,?)""",
            (client_id, data["title"], data["target"],
             data.get("current", 0), data.get("target_date", ""), data.get("note", ""))
        )
        await self._db.commit()
        return cur.lastrowid

    async def delete_goal(self, goal_id: int, client_id: int) -> None:
        await self._db.execute(
            "DELETE FROM goals WHERE id=? AND client_id=?", (goal_id, client_id)
        )
        await self._db.commit()

    async def update_goal_current(self, goal_id: int, client_id: int, current: float) -> None:
        await self._db.execute(
            "UPDATE goals SET current=? WHERE id=? AND client_id=?", (current, goal_id, client_id)
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
