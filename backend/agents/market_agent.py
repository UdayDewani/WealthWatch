from __future__ import annotations

import json
from typing import Any

import google.generativeai as genai

from agents.base_agent import BaseAgent
from config import GEMINI_API_KEYS

# ---------------------------------------------------------------------------
# Key rotation state (module-level so it persists across calls)
# ---------------------------------------------------------------------------
_key_index: int = 0


def _get_current_key() -> str:
    return GEMINI_API_KEYS[_key_index % len(GEMINI_API_KEYS)]


def _rotate_key(logger) -> bool:
    """Advance to the next API key. Returns False when all keys are exhausted."""
    global _key_index
    _key_index += 1
    if _key_index >= len(GEMINI_API_KEYS):
        logger.error("All Gemini API keys have exhausted their quota.")
        return False
    logger.warning("Rotating to Gemini API key #%d", _key_index + 1)
    genai.configure(api_key=_get_current_key())
    return True


# Bootstrap with the first key
genai.configure(api_key=_get_current_key())

# ---------------------------------------------------------------------------
# Prompt / system instruction
# ---------------------------------------------------------------------------
_SYSTEM_INSTRUCTION = """\
You are an expert Indian stock market analyst.
Analyze the given indices (Nifty 50, Sensex, Nifty Bank, Nifty IT), top movers, and recent news.
Determine if the market condition is BULLISH, BEARISH, or NEUTRAL for each index.
Also suggest 3-4 stock recommendations (action: 'buy' or 'hold') for the active stocks.

Return ONLY valid JSON with this exact structure:
{
  "nifty":     { "condition": "bullish|bearish|neutral", "confidence": 0-100, "reasoning": "1 sentence" },
  "sensex":    { "condition": "bullish|bearish|neutral", "confidence": 0-100, "reasoning": "1 sentence" },
  "niftybank": { "condition": "bullish|bearish|neutral", "confidence": 0-100, "reasoning": "1 sentence" },
  "niftyit":   { "condition": "bullish|bearish|neutral", "confidence": 0-100, "reasoning": "1 sentence" },
  "recommendations": [
    { "stock": "Company Name", "symbol": "TICKER", "action": "buy|hold",
      "reason": "1-2 sentence reason", "confidence": 0-100 }
  ],
  "summary": "1 sentence overall market outlook"
}"""

_FALLBACK = {
    "nifty":     {"condition": "neutral", "confidence": 50, "reasoning": "Analysis unavailable."},
    "sensex":    {"condition": "neutral", "confidence": 50, "reasoning": "Analysis unavailable."},
    "niftybank": {"condition": "neutral", "confidence": 50, "reasoning": "Analysis unavailable."},
    "niftyit":   {"condition": "neutral", "confidence": 50, "reasoning": "Analysis unavailable."},
    "recommendations": [
        {"stock": "Reliance Industries", "symbol": "RELIANCE", "action": "hold",
         "reason": "AI analysis offline.", "confidence": 50},
        {"stock": "HDFC Bank", "symbol": "HDFCBANK", "action": "hold",
         "reason": "AI analysis offline.", "confidence": 50},
    ],
    "summary": "AI analysis temporarily unavailable — all Gemini API keys have hit quota limits.",
}


class MarketAnalysisAgent(BaseAgent):
    """
    Analyses live market data with Gemini AI and returns sentiment +
    stock recommendations.  Automatically rotates through all configured
    Gemini API keys on quota errors.
    """

    name = "market_analysis_agent"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_model(self) -> genai.GenerativeModel:
        return genai.GenerativeModel("gemini-2.0-flash", system_instruction=_SYSTEM_INSTRUCTION)

    @staticmethod
    def _build_prompt(market_data: dict) -> str:
        indices = market_data.get("indices", {})
        nifty     = indices.get("nifty") or {}
        sensex    = indices.get("sensex") or {}
        niftybank = indices.get("niftybank") or {}
        niftyit   = indices.get("niftyit") or {}

        news = market_data.get("news", [])
        news_text = "\n".join(f"• {n['title']}" for n in news[:6]) or "No recent news."

        stocks = market_data.get("stocks", {}).get("nifty50", [])
        sorted_s = sorted(stocks, key=lambda s: s.get("change_pct", 0))
        gainers = sorted_s[-3:][::-1]
        losers  = sorted_s[:3]

        def fmt(lst):
            return "\n".join(
                f"• {s['symbol']}: {s['price']} ({s['change_pct']:+.2f}%)" for s in lst
            ) or "N/A"

        return (
            f"INDICES:\n"
            f"- NIFTY 50:   Price={nifty.get('price')}, Change={nifty.get('change')} ({nifty.get('change_pct')}%)\n"
            f"- SENSEX:     Price={sensex.get('price')}, Change={sensex.get('change')} ({sensex.get('change_pct')}%)\n"
            f"- NIFTY BANK: Price={niftybank.get('price')}, Change={niftybank.get('change')} ({niftybank.get('change_pct')}%)\n"
            f"- NIFTY IT:   Price={niftyit.get('price')}, Change={niftyit.get('change')} ({niftyit.get('change_pct')}%)\n\n"
            f"TOP GAINERS:\n{fmt(gainers)}\n\n"
            f"TOP LOSERS:\n{fmt(losers)}\n\n"
            f"RECENT NEWS:\n{news_text}\n\n"
            f"Return JSON only."
        )

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences from Gemini output."""
        if text.startswith("```"):
            lines = text.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])
        return text.strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, market_data: dict, **kwargs) -> dict:
        """
        Analyse *market_data* and return a sentiment + recommendations dict.

        Retries automatically across all available Gemini API keys before
        falling back to a static neutral response.
        """
        task = "market sentiment analysis"
        start = self.log_start(task)
        prompt = self._build_prompt(market_data)

        for _ in range(len(GEMINI_API_KEYS)):
            try:
                model = self._make_model()
                response = await model.generate_content_async(contents=[prompt])
                text = self._strip_fences(response.text.strip())
                result = json.loads(text)
                self.log_done(task, start)
                self.logger.info(
                    "Analysis succeeded with key #%d", (_key_index % len(GEMINI_API_KEYS)) + 1
                )
                return result
            except Exception as exc:
                err = str(exc)
                if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                    self.logger.warning(
                        "Key #%d quota exceeded — rotating.", (_key_index % len(GEMINI_API_KEYS)) + 1
                    )
                    if not _rotate_key(self.logger):
                        break
                else:
                    self.logger.warning("Gemini error (non-quota): %s", exc)
                    break

        self.logger.error("All Gemini keys failed. Returning fallback.")
        return _FALLBACK


# ---------------------------------------------------------------------------
# Backward-compatible module-level function
# ---------------------------------------------------------------------------
_agent = MarketAnalysisAgent()


async def analyze_market(market_data: dict) -> dict:
    """Module-level helper — delegates to MarketAnalysisAgent.run()."""
    return await _agent.run(market_data=market_data)
