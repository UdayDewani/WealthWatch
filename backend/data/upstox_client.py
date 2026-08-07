import json
import httpx
import logging
import os

from config import UPSTOX_API_KEY, UPSTOX_SECRET_KEY, REDIRECT_URI

logger = logging.getLogger("upstox")

UPSTOX_API_BASE = "https://api.upstox.com/v2"
NIFTY_INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"
SENSEX_INSTRUMENT_KEY = "BSE_INDEX|SENSEX"
TOKEN_FILE = "upstox_token.json"


class UpstoxClient:
    def __init__(self):
        self.access_token = None
        # Load persisted token if available
        self._load_token()
        try:
            with open("nifty_constituents.json", "r") as f:
                self.constituents = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load nifty_constituents.json: {e}")
            self.constituents = {"nifty50": [], "niftybank": []}

    def _load_token(self):
        """Load access token from disk if it exists."""
        try:
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    if self.access_token:
                        logger.info("Loaded Upstox access token from disk")
        except Exception as e:
            logger.warning(f"Failed to load token from disk: {e}")

    def _save_token(self):
        """Persist access token to disk."""
        try:
            with open(TOKEN_FILE, "w") as f:
                json.dump({"access_token": self.access_token}, f)
            logger.info("Upstox access token saved to disk")
        except Exception as e:
            logger.warning(f"Failed to save token to disk: {e}")

    def build_auth_url(self):
        return (
            f"{UPSTOX_API_BASE}/login/authorization/dialog"
            f"?client_id={UPSTOX_API_KEY}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
        )

    async def exchange_code(self, auth_code: str):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{UPSTOX_API_BASE}/login/authorization/token",
                headers={
                    "accept": "application/json",
                    "api-version": "2.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "code": auth_code,
                    "client_id": UPSTOX_API_KEY,
                    "client_secret": UPSTOX_SECRET_KEY,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            if resp.status_code != 200:
                logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
                return None
            data = resp.json()
            self.access_token = data.get("access_token")
            logger.info("Upstox access token obtained")
            self._save_token()
            return self.access_token

    async def get_live_index_data(self):
        if not self.access_token:
            logger.warning("No Upstox token, skipping live data")
            return None

        # Build list of instrument keys
        keys = [
            "NSE_INDEX|Nifty 50",
            "BSE_INDEX|SENSEX",
            "NSE_INDEX|Nifty Bank",
            "NSE_INDEX|Nifty IT"
        ]

        # Stocks mapping (ISIN -> metadata) — keyed by instrument_token
        stock_map = {}
        for idx_name, stocks in self.constituents.items():
            for i, s in enumerate(stocks):
                isin = s.get("isin")
                if isin:
                    key = f"NSE_EQ|{isin}"
                    keys.append(key)
                    if key not in stock_map:
                        stock_map[key] = {
                            "symbol": s.get("symbol"),
                            "name": s.get("name"),
                            "index_types": set()
                        }
                    stock_map[key]["index_types"].add(idx_name)

        # De-duplicate keys while preserving order
        unique_keys = list(dict.fromkeys(keys))

        # Batch request up to 100 instruments
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{UPSTOX_API_BASE}/market-quote/quotes",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
                params=[("instrument_key", k) for k in unique_keys[:100]],
            )
            if resp.status_code == 401:
                logger.error("Upstox token expired or invalid (401). Clear token and re-authorize at /auth")
                self.access_token = None
                try:
                    import os as _os
                    if _os.path.exists(TOKEN_FILE):
                        _os.remove(TOKEN_FILE)
                except Exception:
                    pass
                return None
            if resp.status_code != 200:
                logger.warning(f"Quote fetch failed: {resp.status_code} — {resp.text[:300]}")
                return None

            data = resp.json()
            result = {
                "indices": {},
                "stocks": {
                    "nifty50": [],
                    "niftybank": []
                }
            }

            def calc_change_pct(last_price, net_change):
                """Compute % change from last_price and net_change."""
                try:
                    prev = last_price - net_change
                    if prev and prev != 0:
                        return round((net_change / prev) * 100, 2)
                except Exception:
                    pass
                return 0.0

            def parse_index(val):
                last = val.get("last_price") or 0
                chg  = val.get("net_change") or 0
                return {
                    "price":      last,
                    "change":     round(chg, 2),
                    "change_pct": calc_change_pct(last, chg),
                    "volume":     val.get("volume"),
                }

            # NOTE: Upstox returns response keys with colons (NSE_INDEX:Nifty 50)
            # but the instrument_token field inside each record uses pipes (NSE_INDEX|Nifty 50).
            # We match on instrument_token so key format doesn't matter.
            for _resp_key, val in data.get("data", {}).items():
                token = val.get("instrument_token", "")  # e.g. "NSE_INDEX|Nifty 50"

                if token == "NSE_INDEX|Nifty 50":
                    result["indices"]["nifty"] = parse_index(val)
                elif token == "BSE_INDEX|SENSEX":
                    result["indices"]["sensex"] = parse_index(val)
                elif token == "NSE_INDEX|Nifty Bank":
                    result["indices"]["niftybank"] = parse_index(val)
                elif token == "NSE_INDEX|Nifty IT":
                    result["indices"]["niftyit"] = parse_index(val)
                elif token in stock_map:
                    meta = stock_map[token]
                    last = val.get("last_price") or 0
                    chg  = val.get("net_change") or 0
                    stock_item = {
                        "symbol":     meta["symbol"],
                        "name":       meta["name"],
                        "price":      last,
                        "change_pct": calc_change_pct(last, chg),
                        "volume":     val.get("volume"),
                    }
                    if "nifty50" in meta["index_types"]:
                        rank = next(
                            (idx for idx, s in enumerate(self.constituents["nifty50"])
                             if s["symbol"] == meta["symbol"]), 0
                        ) + 1
                        result["stocks"]["nifty50"].append({**stock_item, "rank": rank})
                    if "niftybank" in meta["index_types"]:
                        rank = next(
                            (idx for idx, s in enumerate(self.constituents["niftybank"])
                             if s["symbol"] == meta["symbol"]), 0
                        ) + 1
                        result["stocks"]["niftybank"].append({**stock_item, "rank": rank})

            # Sort stock lists by rank
            result["stocks"]["nifty50"].sort(key=lambda s: s["rank"])
            result["stocks"]["niftybank"].sort(key=lambda s: s["rank"])

            logger.info(
                "Upstox data: %d indices, %d nifty50 stocks, %d niftybank stocks",
                len(result["indices"]),
                len(result["stocks"]["nifty50"]),
                len(result["stocks"]["niftybank"]),
            )
            return result



