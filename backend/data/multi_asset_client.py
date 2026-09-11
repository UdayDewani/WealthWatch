"""
MultiAssetClient — wraps yfinance to fetch live prices for
Stocks, Crypto, Commodities, Forex, ETFs and Mutual Funds.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("multi_asset_client")

# Asset type → yfinance symbol suffix / prefix conventions
ASSET_DEFAULTS: dict[str, list[str]] = {
    "stocks":      ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"],
    "crypto":      ["BTC-USD", "ETH-USD", "BNB-USD"],
    "commodities": ["GC=F", "SI=F", "CL=F"],   # Gold, Silver, Crude Oil futures
    "forex":       ["USDINR=X", "EURUSD=X", "GBPUSD=X"],
    "etfs":        ["NIFTYBEES.NS", "GOLDBEES.NS"],
    "mf":          [],  # MFs are not listed on yfinance; handled separately
}


class MultiAssetClient:
    """Fetches latest price data using yfinance (period='1d', interval='1m')."""

    def __init__(self) -> None:
        try:
            import yfinance as yf  # noqa: F401
            self._yf = yf
            self._available = True
        except ImportError:
            logger.warning("yfinance not installed — MultiAssetClient disabled.")
            self._available = False

    # ── Public helpers ────────────────────────────────────────────────────

    async def get_price(self, symbol: str) -> dict[str, Any] | None:
        """Return {symbol, price, change, change_pct, volume} or None on failure."""
        if not self._available:
            return None
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._fetch_price_sync, symbol)
        except Exception as e:
            logger.warning("Price fetch failed for %s: %s", symbol, e)
            return None

    async def get_prices(self, symbols: list[str]) -> dict[str, Any]:
        """Batch price fetch. Returns {symbol: {...}} dict."""
        if not self._available or not symbols:
            return {}
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._fetch_prices_batch_sync, symbols)
        except Exception as e:
            logger.warning("Batch price fetch failed: %s", e)
            return {}

    async def get_asset_overview(self) -> dict[str, Any]:
        """Returns a snapshot of all default asset categories — all fetched in parallel."""
        import asyncio
        categories = list(ASSET_DEFAULTS.items())

        async def fetch_category(category: str, symbols: list[str]) -> tuple[str, dict]:
            if not symbols:
                return category, {}
            try:
                # 25-second cap per category so one slow call can't block the response
                data = await asyncio.wait_for(self.get_prices(symbols), timeout=25)
            except asyncio.TimeoutError:
                logger.warning("Category '%s' timed out after 25s", category)
                data = {}
            return category, data

        results = await asyncio.gather(
            *[fetch_category(cat, syms) for cat, syms in categories],
            return_exceptions=True,
        )
        out: dict[str, Any] = {}
        for i, res in enumerate(results):
            cat = categories[i][0]
            if isinstance(res, Exception):
                logger.warning("Category '%s' failed: %s", cat, res)
                out[cat] = {}
            else:
                out[cat] = res[1]
        return out

    def _fetch_prices_batch_sync(self, symbols: list[str]) -> dict[str, Any]:
        """Use yfinance batch download (much faster than per-ticker calls)."""
        out: dict[str, Any] = {}
        try:
            import yfinance as yf
            tickers = yf.Tickers(" ".join(symbols))
            for sym in symbols:
                try:
                    ticker = tickers.tickers.get(sym)
                    if ticker is None:
                        continue
                    info = ticker.fast_info
                    price = getattr(info, "last_price", None)
                    prev  = getattr(info, "previous_close", None)
                    if price is None:
                        continue
                    change     = price - prev if prev else 0.0
                    change_pct = (change / prev * 100) if prev else 0.0
                    out[sym] = {
                        "symbol":     sym,
                        "price":      round(price, 4),
                        "change":     round(change, 4),
                        "change_pct": round(change_pct, 4),
                        "volume":     getattr(info, "three_month_average_volume", None),
                    }
                except Exception as e:
                    logger.debug("_fetch_prices_batch_sync error (%s): %s", sym, e)
        except Exception as e:
            logger.warning("_fetch_prices_batch_sync failed: %s — falling back to serial", e)
            # fallback to serial
            for sym in symbols:
                data = self._fetch_price_sync(sym)
                if data:
                    out[sym] = data
        return out

    def _fetch_price_sync(self, symbol: str) -> dict[str, Any] | None:
        try:
            ticker = self._yf.Ticker(symbol)
            info   = ticker.fast_info
            price  = getattr(info, "last_price", None)
            prev   = getattr(info, "previous_close", None)
            if price is None:
                return None
            change     = price - prev if prev else 0.0
            change_pct = (change / prev * 100) if prev else 0.0
            return {
                "symbol":     symbol,
                "price":      round(price, 4),
                "change":     round(change, 4),
                "change_pct": round(change_pct, 4),
                "volume":     getattr(info, "three_month_average_volume", None),
            }
        except Exception as e:
            logger.debug("_fetch_price_sync error (%s): %s", symbol, e)
            return None
