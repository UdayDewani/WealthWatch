from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List

import google.generativeai as genai
import pandas as pd

from agents.base_agent import BaseAgent
from data.database import StockDatabase
from data.yfinance_client import YFinanceClient
from models.stock_analysis import HistoricalPattern, PatternInsight, PriceEvent

# Significant single-day move threshold (absolute %)
_SIGNIFICANT_MOVE_PCT = 2.0

# Cache freshness: re-analyse if data is older than this many hours
_STALE_HOURS = 24

_SYSTEM_INSTRUCTION = """\
You are a senior quantitative analyst specialising in Indian equities.
You will receive a list of significant daily price events (date, price, % change, direction)
for a stock over the last 5 years, along with any known news/reasons for those moves.

Your job is to:
1. Identify recurring behavioural patterns (e.g. "drops before budget", "rallies after earnings",
   "seasonal Q4 strength", "reacts sharply to FII flows", etc.)
2. For each pattern, provide a short name, a 1-2 sentence description, typical frequency,
   and your confidence score (0–100).
3. Write a concise 2-3 sentence AI summary of the stock's historical behaviour.

Return ONLY valid JSON with this exact structure:
{
  "patterns": [
    {
      "pattern_name": "...",
      "description": "...",
      "frequency": "...",
      "confidence": 0-100
    }
  ],
  "ai_summary": "..."
}"""


class HistoricalPatternAgent(BaseAgent):
    """
    Fetches 5 years of daily price history for a stock, identifies significant
    price events (moves > 2 %), sends them to Gemini AI to detect recurring
    patterns, then saves the result to the database.

    Results are cached for 24 hours — a fresh DB hit skips the full pipeline.
    """

    name = "historical_pattern_agent"

    def __init__(self, db: StockDatabase) -> None:
        super().__init__()
        self._db = db
        self._yf = YFinanceClient()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_events(df: pd.DataFrame) -> List[PriceEvent]:
        """Return PriceEvent objects for every daily move > _SIGNIFICANT_MOVE_PCT."""
        if df.empty or "Close" not in df.columns:
            return []

        df = df.copy()
        df["change_pct"] = df["Close"].pct_change() * 100
        events: List[PriceEvent] = []

        for date, row in df.iterrows():
            pct = row["change_pct"]
            if pd.isna(pct) or abs(pct) < _SIGNIFICANT_MOVE_PCT:
                continue
            events.append(
                PriceEvent(
                    date=date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date),
                    price=round(float(row["Close"]), 2),
                    change_pct=round(float(pct), 2),
                    direction="up" if pct > 0 else "down",
                )
            )

        return events

    @staticmethod
    def _build_prompt(symbol: str, events: List[PriceEvent]) -> str:
        lines = [f"Stock: {symbol}", f"Total significant events: {len(events)}", ""]
        for e in events[:120]:  # cap tokens — send at most 120 events
            lines.append(
                f"  {e.date} | {e.direction.upper()} {e.change_pct:+.2f}% | ₹{e.price}"
            )
        return "\n".join(lines) + "\n\nIdentify patterns and return JSON only."

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
        return {"patterns": [], "ai_summary": "Pattern analysis unavailable."}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, symbol: str, period: str = "5y", **kwargs) -> HistoricalPattern:
        """
        Return a HistoricalPattern for *symbol*.

        Serves from DB cache if data is < 24 h old; otherwise runs the
        full scrape-and-analyse pipeline and persists the result.
        """
        task = f"historical pattern analysis [{symbol}, {period}]"
        start = self.log_start(task)

        # --- Cache check ---
        stale = await self._db.is_stale(symbol, "historical_patterns", _STALE_HOURS, period)
        if not stale:
            cached = await self._db.get_history(symbol, period)
            if cached:
                self.logger.info("Cache hit for %s (%s) — skipping pipeline.", symbol, period)
                self.log_done(task, start)
                return cached

        # --- Fetch history ---
        self.logger.info("Fetching %s price history for %s…", period, symbol)
        df = await self._yf.get_price_history(symbol, period)
        events = self._extract_events(df)
        self.logger.info("Found %d significant events for %s.", len(events), symbol)

        # --- Gemini pattern analysis ---
        prompt = self._build_prompt(symbol, events)
        ai_result = await self._call_gemini(prompt)

        patterns = [
            PatternInsight(**p)
            for p in ai_result.get("patterns", [])
            if isinstance(p, dict)
        ]

        pattern = HistoricalPattern(
            symbol=symbol,
            period=period,
            events=events,
            patterns=patterns,
            ai_summary=ai_result.get("ai_summary", ""),
            analyzed_at=datetime.utcnow().isoformat(),
        )

        # --- Persist ---
        await self._db.save_history(pattern)
        self.log_done(task, start)
        return pattern
