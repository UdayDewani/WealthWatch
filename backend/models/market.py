from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class IndexData(BaseModel):
    """Live price snapshot for a single market index."""

    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None


class StockData(BaseModel):
    """Live price snapshot for a single stock constituent."""

    symbol: str
    name: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    rank: int = 0


class StockLists(BaseModel):
    """Grouped stock lists by index membership."""

    nifty50: List[StockData] = Field(default_factory=list)
    niftybank: List[StockData] = Field(default_factory=list)


class IndicesSnapshot(BaseModel):
    """All tracked indices at a single point in time."""

    nifty: Optional[IndexData] = None
    sensex: Optional[IndexData] = None
    niftybank: Optional[IndexData] = None
    niftyit: Optional[IndexData] = None


class NewsItem(BaseModel):
    """A single market news headline."""

    title: str
    publisher: str
    link: str
    published_at: str


class MarketSnapshot(BaseModel):
    """Complete market state — indices, stocks, and news — at a given timestamp."""

    indices: IndicesSnapshot
    stocks: StockLists
    news: List[NewsItem] = Field(default_factory=list)
    timestamp: str
