from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger("yfinance_client")


class YFinanceClient:
    """
    Async wrapper around the synchronous ``yfinance`` library.

    All network calls are executed via ``asyncio.to_thread`` so they never
    block the event loop.  For Indian equities, ``.NS`` is automatically
    appended to the symbol if no exchange suffix is present.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ns_symbol(symbol: str) -> str:
        """Append `.NS` (NSE) suffix for Indian stocks if not already set."""
        return symbol if "." in symbol else f"{symbol}.NS"

    # ------------------------------------------------------------------
    # Price History
    # ------------------------------------------------------------------

    def _fetch_history_sync(self, symbol: str, period: str) -> pd.DataFrame:
        ticker = yf.Ticker(self._ns_symbol(symbol))
        df = ticker.history(period=period, interval="1d")
        return df

    async def get_price_history(
        self, symbol: str, period: str = "5y"
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV data for *symbol* over *period*.

        Returns an empty DataFrame on failure so callers can handle
        gracefully without try/except boilerplate.
        """
        try:
            df = await asyncio.to_thread(self._fetch_history_sync, symbol, period)
            logger.info("Fetched %d rows of history for %s (%s)", len(df), symbol, period)
            return df
        except Exception as exc:
            logger.warning("Price history fetch failed for %s: %s", symbol, exc)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def _fetch_fundamentals_sync(self, symbol: str) -> Dict[str, Any]:
        ticker = yf.Ticker(self._ns_symbol(symbol))
        info: dict = ticker.info or {}

        # --- Latest quarterly revenue & net profit ---
        latest_revenue: Optional[float] = None
        latest_net_profit: Optional[float] = None
        latest_quarter: Optional[str] = None

        try:
            stmt = ticker.quarterly_income_stmt
            if stmt is not None and not stmt.empty:
                col = stmt.columns[0]  # most recent quarter
                latest_quarter = (
                    col.date().isoformat() if hasattr(col, "date") else str(col)
                )
                for rev_key in ("Total Revenue", "Revenue"):
                    if rev_key in stmt.index and pd.notna(stmt.loc[rev_key, col]):
                        latest_revenue = float(stmt.loc[rev_key, col])
                        break
                for profit_key in ("Net Income", "Net Income Common Stockholders"):
                    if profit_key in stmt.index and pd.notna(stmt.loc[profit_key, col]):
                        latest_net_profit = float(stmt.loc[profit_key, col])
                        break
        except Exception as exc:
            logger.debug("Quarterly income statement unavailable for %s: %s", symbol, exc)

        return {
            "quarter": latest_quarter,
            "revenue": latest_revenue,
            "net_profit": latest_net_profit,
            "eps": info.get("trailingEps"),
            "pe_ratio": info.get("trailingPE"),
            "debt_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "market_cap": info.get("marketCap"),
            "book_value": info.get("bookValue"),
            "dividend_yield": info.get("dividendYield"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "name": info.get("longName") or info.get("shortName") or symbol,
        }

    async def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """
        Return a dict of fundamental metrics for *symbol*.

        Includes the most recent quarterly revenue / net profit plus
        standard ratios from the yfinance info dict.
        """
        try:
            data = await asyncio.to_thread(self._fetch_fundamentals_sync, symbol)
            logger.info("Fetched fundamentals for %s", symbol)
            return data
        except Exception as exc:
            logger.warning("Fundamentals fetch failed for %s: %s", symbol, exc)
            return {}

    # ------------------------------------------------------------------
    # Stock-specific news
    # ------------------------------------------------------------------

    def _fetch_stock_news_sync(self, symbol: str) -> List[Dict[str, str]]:
        ticker = yf.Ticker(self._ns_symbol(symbol))
        raw: List[dict] = ticker.news or []
        headlines: List[Dict[str, str]] = []
        for item in raw[:10]:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            ts = item.get("providerPublishTime")
            published_at = "Today"
            if ts:
                try:
                    published_at = datetime.fromtimestamp(int(ts)).strftime(
                        "%d %b, %I:%M %p"
                    )
                except Exception:
                    pass
            headlines.append(
                {
                    "title": title,
                    "publisher": item.get("publisher", "Yahoo Finance"),
                    "link": item.get("link", "#"),
                    "published_at": published_at,
                }
            )
        return headlines

    async def get_stock_news(self, symbol: str) -> List[Dict[str, str]]:
        """Fetch the latest news headlines for a specific stock."""
        try:
            news = await asyncio.to_thread(self._fetch_stock_news_sync, symbol)
            logger.info("Fetched %d news items for %s", len(news), symbol)
            return news
        except Exception as exc:
            logger.warning("Stock news fetch failed for %s: %s", symbol, exc)
            return []
