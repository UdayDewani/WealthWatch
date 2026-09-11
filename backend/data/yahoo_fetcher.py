"""
NewsFetcher — fetches real financial news via yfinance.

Pulls news for major Indian market tickers and deduplicates by URL.
Returns a list of dicts with: title, url, source, published_at.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("yahoo_fetcher")

# Tickers to pull news from (mix of indices + large-caps for broad coverage)
_TICKERS = [
    "^NSEI",        # Nifty 50
    "^BSESN",       # Sensex
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ICICIBANK.NS",
]

_MAX_ITEMS = 15   # max unique headlines to return


class NewsFetcher:
    def __init__(self) -> None:
        try:
            import yfinance as yf  # noqa: F401
            self._yf = yf
            self._available = True
            logger.info("NewsFetcher ready (yfinance)")
        except ImportError:
            logger.warning("yfinance not installed — NewsFetcher disabled")
            self._available = False

    async def fetch_market_news(self) -> list[dict[str, Any]]:
        """
        Fetch and deduplicate news across all tracked tickers.
        Returns list of {title, url, source, published_at} sorted newest-first.
        """
        if not self._available:
            return []
        try:
            return await asyncio.to_thread(self._fetch_sync)
        except Exception as e:
            logger.error("NewsFetcher error: %s", e)
            return []

    async def fetch_stock_news(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch Yahoo Finance articles related to one NSE-listed stock."""
        if not self._available:
            raise RuntimeError("Yahoo Finance news is unavailable")
        try:
            return await asyncio.to_thread(self._fetch_stock_sync, symbol)
        except Exception as exc:
            logger.error("Yahoo Finance stock-news error for %s: %s", symbol, exc)
            raise RuntimeError("Yahoo Finance could not load this stock's news") from exc

    def _normalise_item(self, item: dict) -> dict:
        """Normalise a raw yfinance news item into our standard schema."""
        url = item.get("link") or item.get("url") or ""
        title = item.get("title") or ""
        ts = item.get("providerPublishTime") or item.get("published_at")
        published_at = None
        if ts:
            try:
                from datetime import datetime, timezone
                published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            except Exception:
                pass

        # Simple keyword-based sentiment
        title_lower = title.lower()
        positive_words = ["gain", "rise", "rally", "surge", "high", "beat", "profit", "growth", "up", "positive", "record", "strong"]
        negative_words = ["fall", "drop", "slump", "decline", "loss", "crash", "down", "weak", "miss", "cut", "sell", "fear", "risk"]
        pos_count = sum(1 for w in positive_words if w in title_lower)
        neg_count = sum(1 for w in negative_words if w in title_lower)
        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "title": title,
            "url": url,
            "source": item.get("publisher") or item.get("source") or "Yahoo Finance",
            "published_at": published_at,
            "sentiment": sentiment,
        }

    def _fetch_stock_sync(self, symbol: str) -> list[dict[str, Any]]:
        ticker = self._yf.Ticker(symbol)
        articles = [self._normalise_item(item) for item in (ticker.news or [])]
        return [a for a in articles if a["title"]][:10]

    def _fetch_sync(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        results:   list[dict[str, Any]] = []

        for ticker_sym in _TICKERS:
            try:
                ticker = self._yf.Ticker(ticker_sym)
                raw_news = ticker.news or []
                for item in raw_news:
                    url = item.get("link") or item.get("url") or ""
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = item.get("title") or ""
                    if not title:
                        continue

                    # Convert unix timestamp → ISO string
                    ts = item.get("providerPublishTime") or item.get("published_at")
                    published_at = None
                    if ts:
                        try:
                            published_at = datetime.fromtimestamp(
                                int(ts), tz=timezone.utc
                            ).isoformat()
                        except Exception:
                            pass

                    results.append({
                        "title":        title,
                        "url":          url,
                        "source":       item.get("publisher") or item.get("source") or "Yahoo Finance",
                        "published_at": published_at,
                    })

                    if len(results) >= _MAX_ITEMS:
                        break

            except Exception as e:
                logger.debug("News fetch failed for %s: %s", ticker_sym, e)
                continue

            if len(results) >= _MAX_ITEMS:
                break

        # Sort newest-first (items without timestamp go to the end)
        results.sort(
            key=lambda x: x.get("published_at") or "",
            reverse=True,
        )
        return results[:_MAX_ITEMS]
