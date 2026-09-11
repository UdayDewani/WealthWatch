"""
UpstoxClient — Live Indian market data via Upstox v2 API.

OAuth2 flow (one-time per day):
  1. User visits GET /auth  →  redirected to Upstox login page
  2. User authorises the app
  3. Upstox redirects to GET /callback?code=XXX
  4. Backend calls exchange_code(code) to store the access_token
  5. get_live_index_data() and get_live_stock_prices() return live data

Tokens expire at 3:30 AM IST daily — re-auth needed each day.

Upstox instrument key formats:
  - Indices:  NSE_INDEX|Nifty 50  /  BSE_INDEX|SENSEX
  - NSE EQ:   NSE_EQ|RELIANCE
  - BSE EQ:   BSE_EQ|RELIANCE
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from config import UPSTOX_API_KEY, UPSTOX_SECRET_KEY, UPSTOX_REDIRECT

logger = logging.getLogger("upstox_client")

# ── Instrument key maps ────────────────────────────────────────────────────

INDEX_KEYS: dict[str, str] = {
    "nifty":     "NSE_INDEX|Nifty 50",
    "sensex":    "BSE_INDEX|SENSEX",
    "niftybank": "NSE_INDEX|Nifty Bank",
    "niftyit":   "NSE_INDEX|Nifty IT",
}

# NSE equity stocks — key: friendly name shown in UI, value: Upstox instrument key
STOCK_KEYS: dict[str, str] = {
    "RELIANCE.NS":  "NSE_EQ|INE002A01018",
    "TCS.NS":       "NSE_EQ|INE467B01029",
    "INFY.NS":      "NSE_EQ|INE009A01021",
    "HDFCBANK.NS":  "NSE_EQ|INE040A01034",
    "ICICIBANK.NS": "NSE_EQ|INE090A01021",
    "WIPRO.NS":     "NSE_EQ|INE075A01022",
    "AXISBANK.NS":  "NSE_EQ|INE238A01034",
    "KOTAKBANK.NS": "NSE_EQ|INE237A01028",
    "BAJFINANCE.NS":"NSE_EQ|INE296A01024",
    "HINDUNILVR.NS":"NSE_EQ|INE030A01027",
}

# NSE-listed ETFs
ETF_KEYS: dict[str, str] = {
    "NIFTYBEES.NS": "NSE_EQ|INF204KB14I2",
    "GOLDBEES.NS":  "NSE_EQ|INF204KB17I5",
    "JUNIORBEES.NS":"NSE_EQ|INF732E01045",
}

_AUTH_URL   = "https://api.upstox.com/v2/login/authorization/dialog"
_TOKEN_URL  = "https://api.upstox.com/v2/login/authorization/token"
_QUOTES_URL = "https://api.upstox.com/v2/market-quote/quotes"
_LTP_URL    = "https://api.upstox.com/v2/market-quote/ltp"
_NEWS_URL   = "https://api.upstox.com/v2/news"
_TOKEN_FILE = Path(__file__).resolve().parent.parent / ".upstox_token.json"


class UpstoxClient:
    def __init__(self) -> None:
        if not UPSTOX_API_KEY or not UPSTOX_SECRET_KEY:
            raise ValueError("UPSTOX_API_KEY / UPSTOX_SECRET_KEY not configured")
        self._api_key    = UPSTOX_API_KEY
        self._secret_key = UPSTOX_SECRET_KEY
        self._redirect   = UPSTOX_REDIRECT
        self.access_token = self._load_access_token()
        logger.info("UpstoxClient ready — visit /auth to authorise")

    @staticmethod
    def _load_access_token() -> str:
        """Restore today's OAuth token after a development-server reload."""
        try:
            data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
            token = data.get("access_token", "")
            if token:
                logger.info("Restored Upstox access token from local storage")
            return token
        except (OSError, ValueError, TypeError):
            return ""

    def _save_access_token(self) -> None:
        try:
            _TOKEN_FILE.write_text(
                json.dumps({"access_token": self.access_token}), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("Could not persist Upstox access token: %s", exc)

    # ── OAuth ─────────────────────────────────────────────────────────────

    def build_auth_url(self) -> str:
        """Return the Upstox OAuth authorisation URL."""
        params = {
            "response_type": "code",
            "client_id":     self._api_key,
            "redirect_uri":  self._redirect,
            "state":         "wealthwatch",
        }
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, code: str) -> None:
        """Exchange OAuth code for access token. Stores token in self.access_token."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "code":          code,
                    "client_id":     self._api_key,
                    "client_secret": self._secret_key,
                    "redirect_uri":  self._redirect,
                    "grant_type":    "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data.get("access_token", "")
            if self.access_token:
                self._save_access_token()
                logger.info("Upstox access token obtained successfully")
            else:
                logger.error("Upstox token exchange failed: %s", data)

    # ── Internal quote fetcher ─────────────────────────────────────────────

    async def _fetch_quotes(self, instrument_keys: list[str]) -> dict[str, Any]:
        """
        Call Upstox /market-quote/quotes for a list of instrument keys.
        Returns the raw `data` dict from the API, keyed by instrument_key.
        Returns {} on any error.
        """
        if not self.access_token or not instrument_keys:
            return {}
        keys_csv = ",".join(instrument_keys)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    _QUOTES_URL,
                    params={"instrument_key": keys_csv},
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept":        "application/json",
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("Upstox token expired — please re-authorise at /auth")
                self.access_token = ""
                try:
                    _TOKEN_FILE.unlink(missing_ok=True)
                except OSError:
                    pass
            else:
                logger.error("Upstox API error %s: %s", e.response.status_code, e)
            return {}
        except Exception as e:
            logger.error("Upstox fetch error: %s", e)
            return {}

        if payload.get("status") != "success":
            logger.warning("Upstox non-success response: %s", payload.get("errors"))
            return {}
        data = payload.get("data", {})
        logger.info("Upstox returned %d quote(s): %s", len(data), list(data)[:5])
        return data

    def _parse_quote(self, symbol: str, q: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw Upstox quote dict into our standard price format."""
        price      = q.get("last_price")
        ohlc       = q.get("ohlc", {})
        prev_close = ohlc.get("close") or q.get("close_price")
        net_change = q.get("net_change")

        if net_change is None and price is not None and prev_close:
            net_change = round(price - prev_close, 4)

        change_pct = None
        if net_change is not None and prev_close and prev_close != 0:
            change_pct = round(net_change / prev_close * 100, 4)
        elif q.get("net_change_percentage") is not None:
            change_pct = q["net_change_percentage"]

        return {
            "symbol":     symbol,
            "price":      round(price, 2) if price else 0.0,
            "change":     round(net_change, 2) if net_change is not None else 0.0,
            "change_pct": round(change_pct, 4) if change_pct is not None else 0.0,
            "high":       ohlc.get("high"),
            "low":        ohlc.get("low"),
            "open":       ohlc.get("open"),
            "volume":     q.get("volume"),
        }

    @staticmethod
    def _find_quote(
        quotes: dict[str, Any], instrument_key: str, display_symbol: str = ""
    ) -> dict[str, Any]:
        """Match an Upstox response key to the requested instrument.

        Quote responses use colons (for example ``NSE_EQ:RELIANCE``), while
        requests use pipes and, for equities, the ISIN.  Supporting both forms
        keeps the app aligned with Upstox's documented response shape.
        """
        candidates = {
            instrument_key.casefold(),
            instrument_key.replace("|", ":").casefold(),
        }
        if display_symbol:
            exchange = instrument_key.split("|", 1)[0]
            trading_symbol = display_symbol.removesuffix(".NS").removesuffix(".BO")
            candidates.add(f"{exchange}:{trading_symbol}".casefold())

        for returned_key, quote in quotes.items():
            if returned_key.casefold() in candidates:
                return quote
        return {}

    # ── Public market data methods ─────────────────────────────────────────

    async def get_live_index_data(self) -> dict[str, Any]:
        """
        Fetch live quotes for Nifty 50, Sensex, Nifty Bank, Nifty IT.
        Returns {"indices": {name: {...}}, "stocks": {}}
        """
        quotes = await self._fetch_quotes(list(INDEX_KEYS.values()))
        indices: dict[str, Any] = {}
        for name, key in INDEX_KEYS.items():
            q = self._find_quote(quotes, key)
            if q:
                indices[name] = self._parse_quote(name, q)
                logger.debug("Upstox %s: price=%s", name, indices[name]["price"])
        return {"indices": indices, "stocks": {}}

    async def get_live_stock_prices(
        self,
        key_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Fetch live stock prices from Upstox.
        key_map: {display_symbol: upstox_instrument_key}
                 defaults to STOCK_KEYS (top 10 NSE stocks)
        Returns {display_symbol: {symbol, price, change, change_pct, ...}}
        """
        if key_map is None:
            key_map = STOCK_KEYS
        instrument_keys = list(key_map.values())
        quotes = await self._fetch_quotes(instrument_keys)
        out: dict[str, Any] = {}
        for display_sym, inst_key in key_map.items():
            q = self._find_quote(quotes, inst_key, display_sym)
            if q:
                out[display_sym] = self._parse_quote(display_sym, q)
        return out

    async def get_live_etf_prices(self) -> dict[str, Any]:
        """Fetch live NSE-listed ETF prices from Upstox."""
        return await self.get_live_stock_prices(ETF_KEYS)

    async def get_live_market_assets(self) -> dict[str, dict[str, Any]]:
        """Fetch the complete Markets-page snapshot in one Upstox API call.

        Upstox supplies Indian indices, NSE equities and NSE-listed ETFs. It
        does not provide the crypto, forex, or international commodity feeds
        that the previous Yahoo Finance implementation tried to display.
        """
        quotes = await self._fetch_quotes([
            *INDEX_KEYS.values(),
            *STOCK_KEYS.values(),
            *ETF_KEYS.values(),
        ])

        def parse_category(key_map: dict[str, str]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for symbol, instrument_key in key_map.items():
                quote = self._find_quote(quotes, instrument_key, symbol)
                if quote:
                    out[symbol] = self._parse_quote(symbol, quote)
            return out

        return {
            "indices": parse_category(INDEX_KEYS),
            "stocks": parse_category(STOCK_KEYS),
            "etfs": parse_category(ETF_KEYS),
        }

    async def get_stock_news(self, symbol: str) -> dict[str, Any]:
        """Return all available Upstox news (up to 100 articles) for a stock."""
        instrument_key = STOCK_KEYS.get(symbol)
        if not instrument_key:
            raise ValueError("Unsupported stock symbol")
        if not self.access_token:
            raise PermissionError("Upstox authentication is required")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    _NEWS_URL,
                    params={
                        "category": "instrument_keys",
                        "instrument_keys": instrument_key,
                        "page_number": 1,
                        "page_size": 100,
                    },
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self.access_token = ""
                try:
                    _TOKEN_FILE.unlink(missing_ok=True)
                except OSError:
                    pass
                raise PermissionError("Upstox session expired") from exc
            logger.warning("Upstox news request failed: %s", exc)
            raise RuntimeError("Upstox could not load this stock's news") from exc
        except httpx.HTTPError as exc:
            logger.warning("Upstox news connection failed: %s", exc)
            raise RuntimeError("Upstox could not load this stock's news") from exc

        if payload.get("status") != "success":
            logger.warning("Upstox news returned an error: %s", payload.get("errors"))
            raise RuntimeError("Upstox could not load this stock's news")

        raw_articles = payload.get("data", {}).get(instrument_key, [])
        articles = [
            {
                "title": item.get("heading", "Untitled article"),
                "summary": item.get("summary", ""),
                "thumbnail": item.get("thumbnail", ""),
                "url": item.get("article_link", ""),
                "published_at": item.get("published_time"),
            }
            for item in raw_articles
        ]
        page = payload.get("metadata", {}).get("page", {})
        return {
            "symbol": symbol,
            "source": "upstox",
            "articles": articles,
            "total_records": page.get("total_records", len(articles)),
        }
