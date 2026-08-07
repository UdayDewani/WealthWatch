from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

logger = logging.getLogger("news_fetcher")

# Tickers used for broad market news
_DEFAULT_TICKERS = [
    "^NSEI",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
]

_STATIC_FALLBACK_NEWS = [
    {"title": "Nifty 50 consolidates near record highs; FII inflows support bulls", "publisher": "MoneyControl", "link": "#", "published_at": "Today"},
    {"title": "RBI holds repo rate steady; accommodative stance lifts rate-sensitive stocks", "publisher": "Economic Times", "link": "#", "published_at": "Today"},
    {"title": "Reliance Industries Q4 results beat estimates; stock surges 2%", "publisher": "LiveMint", "link": "#", "published_at": "Today"},
    {"title": "HDFC Bank sees strong credit growth, asset quality remains stable", "publisher": "Business Standard", "link": "#", "published_at": "Today"},
    {"title": "IT sector under pressure as global tech slowdown weighs on outlook", "publisher": "Reuters", "link": "#", "published_at": "Today"},
    {"title": "Nifty Bank index rallies on PSU bank earnings; SBIN leads gains", "publisher": "Financial Express", "link": "#", "published_at": "Today"},
]


def _fmt_timestamp(ts) -> str:
    """Convert a Unix timestamp to a human-readable string."""
    try:
        if ts:
            return datetime.fromtimestamp(int(ts)).strftime("%d %b, %I:%M %p")
    except Exception:
        pass
    return "Today"


class NewsFetcher:
    """
    Fetches financial news from Yahoo Finance for broad market coverage.

    Usage
    -----
    fetcher = NewsFetcher()
    news    = await fetcher.fetch_market_news()          # broad market
    news    = await fetcher.fetch_stock_news("HDFCBANK") # single stock
    """

    def __init__(self, tickers: List[str] | None = None, max_headlines: int = 15) -> None:
        self._tickers = tickers or _DEFAULT_TICKERS
        self._max_headlines = max_headlines

    # ------------------------------------------------------------------
    # Sync internals (run inside thread pool)
    # ------------------------------------------------------------------

    def _fetch_market_news_sync(self) -> List[dict]:
        """Pull headlines across multiple index/stock tickers and deduplicate."""
        try:
            import yfinance as yf

            seen: set[str] = set()
            headlines: List[dict] = []

            for sym in self._tickers:
                try:
                    raw = yf.Ticker(sym).news or []
                    for item in raw:
                        title = (item.get("title") or "").strip()
                        if not title or title in seen:
                            continue
                        seen.add(title)
                        headlines.append(
                            {
                                "title": title,
                                "publisher": item.get("publisher", "Yahoo Finance"),
                                "link": item.get("link", "#"),
                                "published_at": _fmt_timestamp(item.get("providerPublishTime")),
                            }
                        )
                        if len(headlines) >= self._max_headlines:
                            break
                except Exception as exc:
                    logger.debug("News fetch skipped for %s: %s", sym, exc)

                if len(headlines) >= self._max_headlines:
                    break

            if headlines:
                logger.info("Fetched %d market news items from Yahoo Finance", len(headlines))
                return headlines

        except Exception as exc:
            logger.warning("Yahoo Finance news fetch failed: %s", exc)

        logger.info("Using static fallback news")
        return _STATIC_FALLBACK_NEWS

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def fetch_market_news(self) -> List[dict]:
        """
        Asynchronously fetch broad market headlines.

        Falls back to curated static news if Yahoo Finance is unavailable.
        """
        return await asyncio.to_thread(self._fetch_market_news_sync)


# ---------------------------------------------------------------------------
# Module-level singleton for backward compatibility
# ---------------------------------------------------------------------------
_default_fetcher = NewsFetcher()


async def fetch_financial_news() -> List[dict]:
    """Backward-compatible module-level helper — delegates to NewsFetcher."""
    return await _default_fetcher.fetch_market_news()
