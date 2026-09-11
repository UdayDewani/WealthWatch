"""
LangGraph-based market analysis agent.
Graph: analyze → parse → END

Changes vs original:
- LLM is a module-level lazy singleton (not rebuilt every 60 s tick)
- Output schema adds `recommendations` and `risks` aliases for the frontend
- `error` field is actually written on failure
- Prompt includes Upstox index data AND news sources when available
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("langgraph_agent")


# ── State ─────────────────────────────────────────────────────────────────

class MarketState(TypedDict):
    market_data: Dict[str, Any]
    news:        list
    raw_analysis: str
    analysis:    Dict[str, Any]
    error:       str


# ── LLM singleton ─────────────────────────────────────────────────────────
# Built once at module import time; reused across all ticks.

_llm: ChatGoogleGenerativeAI | None = None


def _get_llm() -> ChatGoogleGenerativeAI | None:
    global _llm
    if _llm is not None:
        return _llm
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — LLM analysis disabled")
        return None
    try:
        _llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=0.3,
        )
        logger.info("Gemini LLM initialised (%s)", GEMINI_MODEL)
        return _llm
    except Exception as e:
        logger.warning("LLM init failed: %s", e)
        return None


# ── Nodes ─────────────────────────────────────────────────────────────────

def analyze_node(state: MarketState) -> MarketState:
    """Calls Gemini to analyse market data and news."""
    llm = _get_llm()
    if not llm:
        state["raw_analysis"] = ""
        state["error"] = "LLM unavailable (no API key)"
        return state

    market  = state.get("market_data", {})
    news    = state.get("news", [])
    indices = market.get("indices", {})

    # Build a compact index summary for the prompt
    index_lines = []
    for name, d in indices.items():
        if isinstance(d, dict) and d.get("price"):
            line = (
                f"  {name.upper()}: {d['price']}"
                f"  change={d.get('change', '?')} ({d.get('change_pct', '?')}%)"
            )
            index_lines.append(line)

    indices_text = "\n".join(index_lines) if index_lines else "  (No live index data available)"
    news_text    = "\n".join(
        f"  - [{n.get('source','Yahoo Finance')}] {n.get('title','')}"
        for n in news[:8]
    ) or "  (No news available)"

    prompt = f"""You are an expert Indian market analyst for a wealth management firm.

Current Market Indices:
{indices_text}

Recent News Headlines:
{news_text}

Provide a comprehensive market analysis as valid JSON with EXACTLY these keys:
{{
  "sentiment": "bullish" | "bearish" | "neutral",
  "summary": "2-3 sentence market overview",
  "nifty":     {{"outlook": str, "support": str, "resistance": str}},
  "sensex":    {{"outlook": str, "support": str, "resistance": str}},
  "niftybank": {{"outlook": str}},
  "niftyit":   {{"outlook": str}},
  "key_risks":            ["risk1", "risk2", "risk3"],
  "opportunities":        ["opp1", "opp2", "opp3"],
  "recommended_sectors":  ["sector1", "sector2", "sector3"],
  "recommendations":      ["actionable rec 1", "actionable rec 2", "actionable rec 3"],
  "risks":                ["risk1", "risk2", "risk3"]
}}

Rules:
- `recommendations` should be specific, actionable investment recommendations for today
- `risks` should be the same content as `key_risks` (duplicate for API compatibility)
- Use real current market context from the data provided above
- Return ONLY valid JSON, no markdown code fences
"""
    try:
        response = llm.invoke([
            SystemMessage(content=(
                "You are a professional Indian market analyst. "
                "Always respond with valid JSON only, no markdown."
            )),
            HumanMessage(content=prompt),
        ])
        # gemini-3.6-flash returns content as a list of blocks; extract text robustly
        content = response.content
        if isinstance(content, list):
            raw = " ".join(
                part["text"] if isinstance(part, dict) else str(part)
                for part in content
                if not isinstance(part, dict) or part.get("type") == "text"
            ).strip()
        else:
            raw = str(content).strip()
        # Strip markdown fencing if the model wraps anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        state["raw_analysis"] = raw
        state["error"] = ""
        logger.info("LLM analysis complete (%d chars)", len(raw))
    except Exception as e:
        logger.error("LLM analysis failed: %s", e)
        state["raw_analysis"] = ""
        state["error"] = str(e)
    return state


def parse_node(state: MarketState) -> MarketState:
    """Parse the raw LLM JSON into a structured dict."""
    raw = state.get("raw_analysis", "")
    if not raw:
        state["analysis"] = _fallback_analysis(state.get("market_data", {}))
        return state
    try:
        parsed = json.loads(raw)
        # Ensure both `risks`/`recommendations` AND `key_risks`/`opportunities` exist
        if "key_risks" in parsed and "risks" not in parsed:
            parsed["risks"] = parsed["key_risks"]
        if "opportunities" in parsed and "recommendations" not in parsed:
            parsed["recommendations"] = parsed["opportunities"]
        if "risks" in parsed and "key_risks" not in parsed:
            parsed["key_risks"] = parsed["risks"]
        if "recommendations" in parsed and "opportunities" not in parsed:
            parsed["opportunities"] = parsed["recommendations"]
        state["analysis"] = parsed
    except Exception:
        logger.warning("Failed to parse LLM JSON — using fallback")
        state["analysis"] = _fallback_analysis(state.get("market_data", {}))
    return state


def _fallback_analysis(market: dict) -> dict:
    """Rule-based fallback used when Gemini is unavailable or returns invalid JSON."""
    indices   = market.get("indices", {})
    nifty     = indices.get("nifty", {})
    change    = nifty.get("change_pct") or 0
    sentiment = "bullish" if change > 0.3 else "bearish" if change < -0.3 else "neutral"
    direction = "up" if change >= 0 else "down"
    summary   = (
        f"Markets are {sentiment}. Nifty is {direction} {abs(change):.2f}% today. "
        f"Live AI analysis temporarily unavailable."
    )
    risks = ["Global macro uncertainty", "FII selling pressure", "Rupee depreciation risk"]
    opps  = ["Banking sector resilience", "IT export recovery", "Infrastructure spending"]
    recs  = [
        "Monitor large-cap stocks for entry points",
        "Consider defensive sectors during volatility",
        "Review portfolio hedging positions",
    ]
    sectors = ["Banking", "IT", "FMCG"]
    return {
        "sentiment": sentiment,
        "summary":   summary,
        "nifty":     {"outlook": sentiment, "support": "—", "resistance": "—"},
        "sensex":    {"outlook": sentiment, "support": "—", "resistance": "—"},
        "niftybank": {"outlook": sentiment},
        "niftyit":   {"outlook": sentiment},
        "key_risks":           risks,
        "opportunities":       opps,
        "recommended_sectors": sectors,
        "recommendations":     recs,
        "risks":               risks,
    }


async def summarize_stock_news(symbol: str, articles: list[dict[str, Any]]) -> str:
    """Create a concise, source-grounded summary of Upstox stock news."""
    if not articles:
        return "Upstox has not published any related articles for this stock in the past seven days."

    fallback = " ".join(
        article.get("summary") or article.get("title", "")
        for article in articles[:2]
    ).strip()
    llm = _get_llm()
    if not llm:
        return fallback or f"Upstox returned {len(articles)} related article(s) for {symbol}."

    source_text = "\n".join(
        f"- {article.get('title', '')}: {article.get('summary', '')}"
        for article in articles[:25]
    )
    prompt = f"""Summarise the following Upstox news articles about {symbol} in 2-3 concise sentences.
Only use information present in the articles. Do not make investment recommendations.

Articles:
{source_text}
"""
    try:
        import asyncio
        response = await asyncio.to_thread(llm.invoke, [
            SystemMessage(content="You produce factual, source-grounded financial news summaries."),
            HumanMessage(content=prompt),
        ])
        content = response.content
        if isinstance(content, list):
            text = " ".join(
                part["text"] if isinstance(part, dict) else str(part)
                for part in content
                if not isinstance(part, dict) or part.get("type") == "text"
            ).strip()
        else:
            text = str(content).strip()
        return text or fallback
    except Exception as exc:
        logger.warning("Stock-news summary failed for %s: %s", symbol, exc)
        return fallback or f"Upstox returned {len(articles)} related article(s) for {symbol}."


# ── Graph ─────────────────────────────────────────────────────────────────

def build_market_graph() -> Any:
    g = StateGraph(MarketState)
    g.add_node("analyze", analyze_node)
    g.add_node("parse",   parse_node)
    g.set_entry_point("analyze")
    g.add_edge("analyze", "parse")
    g.add_edge("parse", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_market_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────────────────

async def run_market_analysis(market_data: dict, news: list) -> dict:
    """Run the LangGraph market analysis pipeline. Returns analysis dict."""
    import asyncio
    graph = get_graph()
    initial_state: MarketState = {
        "market_data":  market_data,
        "news":         news,
        "raw_analysis": "",
        "analysis":     {},
        "error":        "",
    }
    try:
        result = await asyncio.to_thread(graph.invoke, initial_state)
        analysis = result.get("analysis", {})
        if not analysis:
            return _fallback_analysis(market_data)
        return analysis
    except Exception as e:
        logger.error("Graph execution failed: %s", e)
        return _fallback_analysis(market_data)
