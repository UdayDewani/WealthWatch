"""
multi_asset_client.py
~~~~~~~~~~~~~~~~~~~~~
Fetches live prices for commodities, crypto, ETFs, mutual funds, and forex
using Yahoo Finance (yfinance) — no extra API keys required.

All heavy network calls run inside asyncio.to_thread so they never block
the FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

import yfinance as yf

logger = logging.getLogger("multi_asset")

# ---------------------------------------------------------------------------
# Symbol registries
# ---------------------------------------------------------------------------

COMMODITIES: List[Dict[str, str]] = [
    {"symbol": "GC=F",  "name": "Gold",          "unit": "USD/oz",  "icon": "🥇"},
    {"symbol": "SI=F",  "name": "Silver",         "unit": "USD/oz",  "icon": "🥈"},
    {"symbol": "CL=F",  "name": "Crude Oil",      "unit": "USD/bbl", "icon": "🛢️"},
    {"symbol": "NG=F",  "name": "Natural Gas",    "unit": "USD/MMBtu","icon": "🔥"},
    {"symbol": "HG=F",  "name": "Copper",         "unit": "USD/lb",  "icon": "🔶"},
    {"symbol": "ALI=F", "name": "Aluminium",      "unit": "USD/lb",  "icon": "⚙️"},
]

CRYPTO: List[Dict[str, str]] = [
    {"symbol": "BTC-USD", "name": "Bitcoin",   "icon": "₿"},
    {"symbol": "ETH-USD", "name": "Ethereum",  "icon": "Ξ"},
    {"symbol": "SOL-USD", "name": "Solana",    "icon": "◎"},
    {"symbol": "BNB-USD", "name": "BNB",       "icon": "🔶"},
    {"symbol": "XRP-USD", "name": "XRP",       "icon": "✕"},
    {"symbol": "ADA-USD", "name": "Cardano",   "icon": "₳"},
    {"symbol": "DOGE-USD","name": "Dogecoin",  "icon": "🐕"},
    {"symbol": "AVAX-USD","name": "Avalanche", "icon": "🔺"},
]

FOREX: List[Dict[str, str]] = [
    {"symbol": "USDINR=X", "name": "USD / INR", "base": "USD", "quote": "INR"},
    {"symbol": "EURINR=X", "name": "EUR / INR", "base": "EUR", "quote": "INR"},
    {"symbol": "GBPINR=X", "name": "GBP / INR", "base": "GBP", "quote": "INR"},
    {"symbol": "JPYINR=X", "name": "JPY / INR", "base": "JPY", "quote": "INR"},
    {"symbol": "AUDINR=X", "name": "AUD / INR", "base": "AUD", "quote": "INR"},
    {"symbol": "CADINR=X", "name": "CAD / INR", "base": "CAD", "quote": "INR"},
]

ETFS: List[Dict[str, str]] = [
    {"symbol": "NIFTYBEES.NS",  "name": "Nippon India Nifty BeES",    "category": "Equity"},
    {"symbol": "GOLDBEES.NS",   "name": "Nippon India Gold BeES",      "category": "Commodity"},
    {"symbol": "BANKBEES.NS",   "name": "Nippon India Bank BeES",      "category": "Equity"},
    {"symbol": "JUNIORBEES.NS", "name": "Nippon India Junior BeES",    "category": "Equity"},
    {"symbol": "LIQUIDBEES.NS", "name": "Nippon India Liquid BeES",    "category": "Debt"},
    {"symbol": "ICICIB22.NS",   "name": "ICICI Pru Bharat Bond 2032", "category": "Debt"},
    {"symbol": "ITBEES.NS",     "name": "Nippon India IT BeES",        "category": "Equity"},
    {"symbol": "SILVERBEES.NS", "name": "Nippon India Silver ETF",     "category": "Commodity"},
]

MUTUAL_FUNDS: List[Dict[str, str]] = [
    {"symbol": "0P0001IVHX.BO", "name": "HDFC Flexi Cap Fund",              "category": "Equity – Flexi Cap"},
    {"symbol": "0P0000XVK0.BO", "name": "Mirae Asset Emerging Bluechip",    "category": "Equity – Large & Mid"},
    {"symbol": "0P0001FDZE.BO", "name": "Parag Parikh Flexi Cap Fund",      "category": "Equity – Flexi Cap"},
    {"symbol": "0P0000XVKJ.BO", "name": "Axis Bluechip Fund",               "category": "Equity – Large Cap"},
    {"symbol": "0P0000XVGW.BO", "name": "SBI Small Cap Fund",               "category": "Equity – Small Cap"},
    {"symbol": "0P00005WJ0.BO", "name": "ICICI Pru Balanced Advantage",     "category": "Hybrid – Balanced"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_pct(info: dict, key: str) -> float | None:
    v = info.get(key)
    return round(float(v) * 100, 2) if v is not None else None


def _parse_ticker(sym: str, meta: Dict[str, str]) -> Dict[str, Any] | None:
    """Fetch a single ticker and return a normalised dict."""
    try:
        t = yf.Ticker(sym)
        info: dict = t.fast_info  # type: ignore[assignment]

        # fast_info is a FastInfo object — access attrs
        price = getattr(info, "last_price", None) or getattr(info, "regular_market_price", None)
        prev  = getattr(info, "previous_close", None) or getattr(info, "regular_market_previous_close", None)

        if price is None:
            return None

        change     = round(price - prev, 4)        if prev else 0.0
        change_pct = round((change / prev) * 100, 2) if prev else 0.0

        return {
            **meta,
            "price":      round(float(price), 4),
            "change":     change,
            "change_pct": change_pct,
            "prev_close": round(float(prev), 4) if prev else None,
        }
    except Exception as exc:
        logger.debug("Failed to fetch %s: %s", sym, exc)
        return None


def _fetch_category_sync(items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Fetch all symbols in a category synchronously (called via to_thread)."""
    results = []
    for meta in items:
        row = _parse_ticker(meta["symbol"], meta)
        if row:
            results.append(row)
    return results


def _fetch_batch_sync(
    items: List[Dict[str, str]],
    extra_fields: dict | None = None,
) -> List[Dict[str, Any]]:
    """Batch-download tickers using yf.download for speed."""
    symbols = [m["symbol"] for m in items]
    meta_map = {m["symbol"]: m for m in items}
    results = []
    try:
        # download 1d data — gives us close + prev_close cheaply
        df = yf.download(
            symbols,
            period="2d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        for sym in symbols:
            try:
                # Multi-ticker df has MultiIndex columns
                closes = df["Close"][sym].dropna() if len(symbols) > 1 else df["Close"].dropna()
                if len(closes) < 1:
                    continue
                price = float(closes.iloc[-1])
                prev  = float(closes.iloc[-2]) if len(closes) >= 2 else price
                change     = round(price - prev, 4)
                change_pct = round((change / prev) * 100, 2) if prev else 0.0
                row = {
                    **meta_map[sym],
                    "price":      round(price, 4),
                    "change":     change,
                    "change_pct": change_pct,
                    "prev_close": round(prev, 4),
                    **(extra_fields or {}),
                }
                results.append(row)
            except Exception as exc:
                logger.debug("Parse failed for %s: %s", sym, exc)
    except Exception as exc:
        logger.warning("Batch download failed: %s — falling back to per-ticker", exc)
        results = _fetch_category_sync(items)
    return results


# ---------------------------------------------------------------------------
# Public client
# ---------------------------------------------------------------------------

class MultiAssetClient:
    """
    Provides a single ``get_all_assets()`` coroutine that returns live prices
    for commodities, crypto, forex, ETFs, and mutual funds.

    Data is fetched concurrently using asyncio.gather over thread pool tasks,
    so the total wall-clock time is roughly equal to the slowest category fetch.
    """

    async def _fetch(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(_fetch_batch_sync, items)

    async def get_all_assets(self) -> Dict[str, Any]:
        """
        Returns a dict::

            {
                "commodities": [...],
                "crypto":      [...],
                "forex":       [...],
                "etfs":        [...],
                "mutual_funds":[...],
                "timestamp":   "<ISO-8601 UTC>",
            }
        """
        logger.info("Fetching multi-asset data from Yahoo Finance…")
        t0 = datetime.utcnow()

        commodities, crypto, forex, etfs, mfs = await asyncio.gather(
            self._fetch(COMMODITIES),
            self._fetch(CRYPTO),
            self._fetch(FOREX),
            self._fetch(ETFS),
            self._fetch(MUTUAL_FUNDS),
            return_exceptions=False,
        )

        elapsed = (datetime.utcnow() - t0).total_seconds()
        logger.info(
            "Multi-asset fetch complete in %.1fs — "
            "%d commodities, %d crypto, %d forex, %d ETFs, %d MFs",
            elapsed, len(commodities), len(crypto), len(forex), len(etfs), len(mfs),
        )

        return {
            "commodities":  commodities,
            "crypto":       crypto,
            "forex":        forex,
            "etfs":         etfs,
            "mutual_funds": mfs,
            "timestamp":    datetime.utcnow().isoformat() + "Z",
        }
