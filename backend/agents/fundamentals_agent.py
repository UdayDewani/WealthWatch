from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List

import google.generativeai as genai

from agents.base_agent import BaseAgent
from data.database import StockDatabase
from data.yfinance_client import YFinanceClient
from models.stock_analysis import Fundamentals, StockNewsItem, StockProfile

# Cache freshness: re-analyse if data is older than this many hours
_STALE_HOURS = 6

_SYSTEM_INSTRUCTION = """\
You are a fundamental analyst covering Indian equities.
You will receive a stock's latest quarterly financial metrics and its most recent news headlines.

Your job is to write a concise 3-4 sentence AI summary covering:
1. The stock's current financial health (revenue trend, profitability, valuation)
2. Key risks or tailwinds from the news
3. An overall current-condition verdict (Positive / Cautious / Negative)

Return ONLY valid JSON:
{
  "ai_summary": "..."
}"""


class FundamentalsAgent(BaseAgent):
    """
    Fetches last-quarter fundamentals and latest stock-specific news for a
    ticker, generates an AI summary via Gemini, and caches the full
    StockProfile in SQLite.

    Results are cached for 6 hours — a fresh DB hit skips the full pipeline.
    """

    name = "fundamentals_agent"

    def __init__(self, db: StockDatabase) -> None:
        super().__init__()
        self._db = db
        self._yf = YFinanceClient()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(symbol: str, fundamentals: dict, news: List[dict]) -> str:
        fin = (
            f"Symbol: {symbol}\n"
            f"Quarter: {fundamentals.get('quarter', 'N/A')}\n"
            f"Revenue: ₹{fundamentals.get('revenue', 'N/A')}\n"
            f"Net Profit: ₹{fundamentals.get('net_profit', 'N/A')}\n"
            f"EPS: {fundamentals.get('eps', 'N/A')}\n"
            f"P/E Ratio: {fundamentals.get('pe_ratio', 'N/A')}\n"
            f"Debt/Equity: {fundamentals.get('debt_equity', 'N/A')}\n"
            f"ROE: {fundamentals.get('roe', 'N/A')}\n"
            f"Market Cap: ₹{fundamentals.get('market_cap', 'N/A')}\n"
        )
        news_lines = "\n".join(f"• {n['title']}" for n in news[:8]) or "No recent news."
        return f"{fin}\nRECENT NEWS:\n{news_lines}\n\nReturn JSON only."

    async def _call_gemini(self, prompt: str) -> dict:
        """Call Gemini with key rotation and return parsed JSON."""
        from config import GEMINI_API_KEYS

        key_index = 0
        for _ in range(len(GEMINI_API_KEYS)):
            try:
                genai.configure(api_key=GEMINI_API_KEYS[key_index % len(GEMINI_API_KEYS)])
                model = genai.GenerativeModel(
                    "gemini-2.0-flash", system_instruction=_SYSTEM_INSTRUCTION
                )
                resp = await model.generate_content_async(contents=[prompt])
                text = resp.text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    end = -1 if lines[-1].strip() == "```" else len(lines)
                    text = "\n".join(lines[1:end]).strip()
                return json.loads(text)
            except Exception as exc:
                err = str(exc)
                if "429" in err or "quota" in err.lower():
                    key_index += 1
                    self.logger.warning("Quota exceeded — rotating key.")
                else:
                    self.logger.warning("Gemini error: %s", exc)
                    break
        return {"ai_summary": "Fundamentals analysis unavailable."}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, symbol: str, **kwargs) -> StockProfile:
        """
        Return a StockProfile for *symbol*.

        Serves from DB cache if data is < 6 h old; otherwise runs the
        full fetch-and-analyse pipeline and persists the result.
        """
        task = f"fundamentals analysis [{symbol}]"
        start = self.log_start(task)

        # --- Cache check ---
        stale = await self._db.is_stale(symbol, "stock_profiles", _STALE_HOURS)
        if not stale:
            cached = await self._db.get_profile(symbol)
            if cached:
                self.logger.info("Cache hit for %s — skipping pipeline.", symbol)
                self.log_done(task, start)
                return cached

        # --- Fetch data in parallel ---
        self.logger.info("Fetching fundamentals + news for %s…", symbol)
        import asyncio
        fundamentals_raw, news_raw = await asyncio.gather(
            self._yf.get_fundamentals(symbol),
            self._yf.get_stock_news(symbol),
        )

        # --- Build Fundamentals model ---
        fundamentals = Fundamentals(
            symbol=symbol,
            quarter=fundamentals_raw.get("quarter"),
            revenue=fundamentals_raw.get("revenue"),
            net_profit=fundamentals_raw.get("net_profit"),
            eps=fundamentals_raw.get("eps"),
            pe_ratio=fundamentals_raw.get("pe_ratio"),
            debt_equity=fundamentals_raw.get("debt_equity"),
            roe=fundamentals_raw.get("roe"),
            market_cap=fundamentals_raw.get("market_cap"),
            book_value=fundamentals_raw.get("book_value"),
            dividend_yield=fundamentals_raw.get("dividend_yield"),
        )

        news_items = [StockNewsItem(**n) for n in news_raw]

        # --- Gemini AI summary ---
        prompt = self._build_prompt(symbol, fundamentals_raw, news_raw)
        ai_result = await self._call_gemini(prompt)

        profile = StockProfile(
            symbol=symbol,
            name=fundamentals_raw.get("name", symbol),
            current_price=fundamentals_raw.get("current_price"),
            fundamentals=fundamentals,
            recent_news=news_items,
            ai_summary=ai_result.get("ai_summary", ""),
            analyzed_at=datetime.utcnow().isoformat(),
        )

        # --- Persist ---
        await self._db.save_profile(profile)
        self.log_done(task, start)
        return profile
