from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict

from agents.base_agent import BaseAgent
from agents.market_agent import MarketAnalysisAgent
from agents.history_agent import HistoricalPatternAgent
from agents.fundamentals_agent import FundamentalsAgent
from data.database import StockDatabase
from data.yahoo_fetcher import NewsFetcher
from models.stock_analysis import HistoricalPattern, StockProfile

logger = logging.getLogger("orchestrator")


class Orchestrator:
    """
    Central task router — the sole entry-point that ``main.py`` interacts with.

    All specialist agents are registered in a task registry.  Callers use
    ``dispatch()`` for ad-hoc tasks or the higher-level helpers
    ``run_pipeline()`` and ``analyze_stock()`` for common workflows.

    Task Registry
    -------------
    "analyze_market"       → MarketAnalysisAgent
    "analyze_history"      → HistoricalPatternAgent
    "analyze_fundamentals" → FundamentalsAgent
    """

    def __init__(self, db: StockDatabase) -> None:
        self._db = db
        self._news_fetcher = NewsFetcher()

        # Instantiate all agents
        self.market_agent       = MarketAnalysisAgent()
        self.history_agent      = HistoricalPatternAgent(db)
        self.fundamentals_agent = FundamentalsAgent(db)

        # Task → agent registry
        self._registry: Dict[str, BaseAgent] = {
            "analyze_market":       self.market_agent,
            "analyze_history":      self.history_agent,
            "analyze_fundamentals": self.fundamentals_agent,
        }

        logger.info(
            "Orchestrator initialised — registered tasks: %s",
            list(self._registry.keys()),
        )

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, task: str, **kwargs) -> Any:
        """
        Route a named *task* to the correct agent and return its result.

        Parameters
        ----------
        task   : One of the registered task names (see class docstring).
        kwargs : Passed through directly to the agent's ``run()`` method.

        Raises
        ------
        ValueError if *task* is not registered.
        """
        agent = self._registry.get(task)
        if agent is None:
            available = list(self._registry.keys())
            raise ValueError(
                f"Unknown task '{task}'. Available tasks: {available}"
            )

        start = time.monotonic()
        logger.info("Dispatching '%s' → %s", task, agent.name)
        result = await agent.run(**kwargs)
        elapsed = time.monotonic() - start
        logger.info("'%s' completed in %.2fs", task, elapsed)
        return result

    # ------------------------------------------------------------------
    # High-level workflows
    # ------------------------------------------------------------------

    async def run_pipeline(self, upstox_data: dict) -> dict:
        """
        Full market analysis pipeline — called by the 60-second loop in main.py.

        Steps (run concurrently where possible)
        ----------------------------------------
        1. Fetch market news             (NewsFetcher)
        2. Build MarketSnapshot
        3. Run MarketAnalysisAgent       (Gemini AI sentiment + recommendations)
        4. Return broadcast-ready dict
        """
        start = time.monotonic()
        logger.info("Running full market pipeline…")

        # News fetch runs while we build the market snapshot
        news = await self._news_fetcher.fetch_market_news()

        market_data = {
            "indices": upstox_data.get("indices", {}),
            "stocks":  upstox_data.get("stocks", {}),
            "news":    news,
            "timestamp": datetime.utcnow().isoformat(),
        }

        analysis = await self.dispatch("analyze_market", market_data=market_data)

        broadcast = {
            "auth_required": False,
            "indices":  market_data["indices"],
            "stocks":   market_data["stocks"],
            # Backward-compat keys
            "nifty":    market_data["indices"].get("nifty"),
            "sensex":   market_data["indices"].get("sensex"),
            "news":     market_data["news"],
            "analysis": analysis,
            "summary":  analysis.get("summary", ""),
            "timestamp": market_data["timestamp"],
        }

        logger.info("Pipeline completed in %.2fs", time.monotonic() - start)
        return broadcast

    async def analyze_stock(self, symbol: str, period: str = "5y") -> dict:
        """
        Full stock deep-dive — historical patterns + fundamentals run in parallel.

        Returns a combined dict:
        {
            "symbol":  str,
            "profile": StockProfile,
            "history": HistoricalPattern,
        }
        """
        start = time.monotonic()
        logger.info("Running full stock analysis for %s…", symbol)

        history, profile = await asyncio.gather(
            self.dispatch("analyze_history",      symbol=symbol, period=period),
            self.dispatch("analyze_fundamentals", symbol=symbol),
        )

        result = {
            "symbol":  symbol,
            "profile": profile.model_dump() if isinstance(profile, StockProfile) else profile,
            "history": history.model_dump() if isinstance(history, HistoricalPattern) else history,
        }

        logger.info("Stock analysis for %s completed in %.2fs", symbol, time.monotonic() - start)
        return result

    # ------------------------------------------------------------------
    # Registry inspection
    # ------------------------------------------------------------------

    def list_tasks(self) -> list[str]:
        """Return the names of all registered tasks."""
        return list(self._registry.keys())
