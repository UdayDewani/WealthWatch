from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PriceEvent(BaseModel):
    """A single significant price movement in a stock's history."""

    date: str
    price: float
    change_pct: float
    direction: str  # "up" or "down"
    reason: Optional[str] = None  # AI-inferred cause


class PatternInsight(BaseModel):
    """A recurring behavioural pattern identified in a stock's history."""

    pattern_name: str
    description: str
    frequency: Optional[str] = None  # e.g. "quarterly", "around earnings"
    confidence: int = Field(ge=0, le=100)


class HistoricalPattern(BaseModel):
    """Full historical pattern analysis result for a stock."""

    symbol: str
    period: str  # e.g. "5y"
    events: List[PriceEvent] = Field(default_factory=list)
    patterns: List[PatternInsight] = Field(default_factory=list)
    ai_summary: str = ""
    analyzed_at: str  # ISO-8601 UTC timestamp


class Fundamentals(BaseModel):
    """Key fundamental metrics from the latest quarterly filing."""

    symbol: str
    quarter: Optional[str] = None          # e.g. "2024-03-31"
    revenue: Optional[float] = None        # INR
    net_profit: Optional[float] = None     # INR
    eps: Optional[float] = None            # Earnings per share
    pe_ratio: Optional[float] = None       # Trailing P/E
    debt_equity: Optional[float] = None    # Debt-to-equity ratio
    roe: Optional[float] = None            # Return on equity (fraction)
    market_cap: Optional[float] = None     # INR
    book_value: Optional[float] = None     # Per share
    dividend_yield: Optional[float] = None # Fraction


class StockNewsItem(BaseModel):
    """A single news headline related to a specific stock."""

    title: str
    publisher: str
    link: str
    published_at: str


class StockProfile(BaseModel):
    """Complete current-condition profile for a stock — fundamentals + news + AI summary."""

    symbol: str
    name: str
    current_price: Optional[float] = None
    fundamentals: Optional[Fundamentals] = None
    recent_news: List[StockNewsItem] = Field(default_factory=list)
    ai_summary: str = ""
    analyzed_at: str  # ISO-8601 UTC timestamp
