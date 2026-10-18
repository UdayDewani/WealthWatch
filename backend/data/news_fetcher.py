"""
NewsFetcher — SearXNG + Firecrawl + Gemini pipeline.

Flow for stock news:
  1. SearXNG  → search "{symbol} stock news India" → get top URLs
  2. Firecrawl → scrape each URL → get markdown content
  3. Gemini LLM → summarise content → return structured articles + summary

Flow for market news:
  Same but query = "Nifty Sensex Indian stock market news today"
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger("news_fetcher")

# ── Config (imported lazily so module loads even without .env) ─────────────
def _cfg():
    from config import SEARXNG_BASE, FIRECRAWL_BASE, FIRECRAWL_KEY
    return SEARXNG_BASE, FIRECRAWL_BASE, FIRECRAWL_KEY


# ── Helpers ────────────────────────────────────────────────────────────────

def _sentiment(text: str) -> str:
    t = text.lower()
    pos = sum(1 for w in ["gain","rise","rally","surge","high","beat","profit",
                          "growth","up","positive","record","strong","bull","buy","upgrade"] if w in t)
    neg = sum(1 for w in ["fall","drop","slump","decline","loss","crash","down",
                          "weak","miss","cut","sell","fear","risk","bear","downgrade"] if w in t)
    return "positive" if pos > neg else "negative" if neg > pos else "neutral"


def _clean_md(text: str) -> str:
    """Strip markdown noise, keep first ~2000 chars for LLM context."""
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)          # images
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text) # links → text
    text = re.sub(r"#{1,6}\s*", "", text)                 # headings
    text = re.sub(r"\n{3,}", "\n\n", text)                # blank lines
    return text.strip()[:2000]


# ── Main class ─────────────────────────────────────────────────────────────

class NewsFetcher:
    """SearXNG + Firecrawl + Gemini news pipeline."""

    def __init__(self) -> None:
        self._searxng, self._firecrawl, self._fc_key = _cfg()
        self._llm = None
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config import GEMINI_API_KEY, GEMINI_MODEL
            if GEMINI_API_KEY:
                self._llm = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    google_api_key=GEMINI_API_KEY,
                    temperature=0.3,
                )
        except Exception as exc:
            logger.warning("LLM unavailable for news summarisation: %s", exc)

        logger.info("NewsFetcher ready (SearXNG=%s  Firecrawl=%s)",
                    self._searxng, self._firecrawl)

    # ── Public API ──────────────────────────────────────────────────────────

    async def fetch_stock_news(self, symbol: str) -> list[dict[str, Any]]:
        """Return articles + AI summary for a specific stock symbol."""
        company = symbol.upper().replace(".NS", "").replace(".BO", "")
        query   = f"{company} stock market news India latest"
        return await self._pipeline(query, max_results=4)

    async def fetch_market_news(self) -> list[dict[str, Any]]:
        """Return broad Indian market news articles."""
        query = "Nifty 50 Sensex Indian stock market news today"
        return await self._pipeline(query, max_results=5)

    async def summarize(self, symbol: str, articles: list[dict]) -> str:
        """Generate an LLM summary from already-fetched articles."""
        if not articles:
            return ""
        combined = "\n\n".join(
            f"Headline: {a.get('title','')}\n{a.get('_content','')}"
            for a in articles
        )
        return await self._llm_summarize(symbol, combined)

    # ── Internal pipeline ───────────────────────────────────────────────────

    async def _pipeline(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        """Full pipeline with a hard 28-second overall timeout."""
        try:
            return await asyncio.wait_for(
                self._pipeline_inner(query, max_results),
                timeout=28,
            )
        except asyncio.TimeoutError:
            logger.warning("News pipeline timed out for query: %s", query)
            return []

    async def _pipeline_inner(self, query: str, max_results: int) -> list[dict[str, Any]]:
        # Step 1 — Search
        search_results = await self._search(query)
        if not search_results:
            logger.warning("SearXNG returned no results for: %s", query)
            return []

        # Step 2 — Scrape top N concurrently (cap at 3 to stay within timeout)
        top = search_results[:min(max_results, 3)]
        scraped = await asyncio.gather(
            *[self._scrape(r.get("url", "")) for r in top],
            return_exceptions=True,
        )

        articles: list[dict] = []
        all_content_parts: list[str] = []

        for r, content in zip(top, scraped):
            url   = r.get("url", "")
            title = r.get("title", "").strip()
            if not url or not title:
                continue
            raw_content = content if isinstance(content, str) else ""
            clean       = _clean_md(raw_content)

            articles.append({
                "title":        title,
                "url":          url,
                "source":       _extract_domain(url),
                "published_at": None,
                "sentiment":    _sentiment(title),
                "_content":     clean,
            })
            if clean:
                all_content_parts.append(f"Headline: {title}\n{clean}")

        if not articles:
            return []

        # Step 3 — LLM summary.
        # Use scraped content if available; fall back to headlines-only so the
        # summary is ALWAYS generated even when Firecrawl returns empty content.
        summary_text = ""
        if self._llm:
            if all_content_parts:
                # Rich summary from scraped article bodies
                llm_input = "\n\n---\n\n".join(all_content_parts)
            else:
                # Headline-only fallback — still useful context for the LLM
                llm_input = "Headlines only (article bodies unavailable):\n" + "\n".join(
                    f"- {a['title']}" for a in articles
                )
            try:
                summary_text = await asyncio.wait_for(
                    self._llm_summarize(query, llm_input), timeout=15
                )
                logger.info("LLM summary generated (%d chars)", len(summary_text))
            except asyncio.TimeoutError:
                logger.warning("LLM summarise timed out")

        # Attach summary to first article; strip internal _content key
        result = []
        for i, a in enumerate(articles):
            clean_a = {k: v for k, v in a.items() if k != "_content"}
            if i == 0:
                clean_a["summary"] = summary_text
            result.append(clean_a)

        return result

    # ── SearXNG ─────────────────────────────────────────────────────────────

    async def _search(self, query: str) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    self._searxng,
                    params={"q": query, "format": "json",
                            "categories": "news,general", "language": "en"},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                logger.debug("SearXNG: %d results for '%s'", len(results), query)
                return results
        except Exception as exc:
            logger.error("SearXNG error for '%s': %s", query, exc)
            return []

    # ── Firecrawl ───────────────────────────────────────────────────────────

    async def _scrape(self, url: str) -> str:
        if not url:
            return ""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._fc_key:
            headers["Authorization"] = f"Bearer {self._fc_key}"
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.post(
                    f"{self._firecrawl}/v2/scrape",   # v2 is the current API version
                    json={
                        "url": url,
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                        "timeout": 8000,   # ms, matches httpx timeout
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                # v2 response: { success: true, data: { markdown: "..." } }
                inner = data.get("data") or data
                md = inner.get("markdown") or inner.get("content") or ""
                logger.debug("Firecrawl scraped %d chars from %s", len(md), url)
                return md
        except Exception as exc:
            logger.debug("Firecrawl error for %s: %s", url, exc)
            return ""

    # ── Gemini summary ──────────────────────────────────────────────────────

    async def _llm_summarize(self, topic: str, content: str) -> str:
        if not self._llm:
            return ""
        prompt = (
            f"You are a financial news analyst. Based on the following recent news articles "
            f"about '{topic}', write a concise 2-3 sentence summary of the key developments, "
            f"market sentiment, and any notable risks or opportunities. "
            f"Be factual and objective.\n\n"
            f"Articles:\n{content[:4000]}\n\n"
            f"Summary:"
        )
        try:
            result = await asyncio.to_thread(self._llm.invoke, prompt)
            # LangChain AIMessage — extract text
            text = getattr(result, "content", str(result))
            if isinstance(text, list):
                text = " ".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in text
                )
            return str(text).strip()
        except Exception as exc:
            logger.error("LLM summarise error: %s", exc)
            return ""


# ── Utility ────────────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    """Extract readable domain name from a URL."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        # Strip www. prefix
        return host.removeprefix("www.")
    except Exception:
        return "News"
