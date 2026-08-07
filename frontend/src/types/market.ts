export interface IndexData {
  symbol?: string;
  price: number;
  change: number;
  change_pct: number;
  volume?: number;
  high?: number;
  low?: number;
  open?: number;
  prev_close?: number;
}

export interface NewsItem {
  title: string;
  link?: string;
  publisher?: string;
}

export interface IndexAnalysis {
  condition: 'bullish' | 'bearish' | 'neutral';
  confidence: number;
  reasoning: string;
}

export interface Recommendation {
  stock: string;
  symbol: string;
  action: 'buy' | 'hold';
  reason: string;
  confidence: number;
}

export interface Analysis {
  nifty: IndexAnalysis;
  sensex: IndexAnalysis;
  niftybank?: IndexAnalysis;
  niftyit?: IndexAnalysis;
  recommendations?: Recommendation[];
  summary?: string;
}

export interface Stock {
  rank: number;
  name: string;
  symbol: string;
  price: number;
  change_pct: number;
  volume: number;
}

export interface MarketData {
  indices?: {
    nifty: IndexData;
    sensex: IndexData;
    niftybank: IndexData;
    niftyit: IndexData;
  };
  stocks?: {
    nifty50: Stock[];
    niftybank: Stock[];
  };
  nifty: IndexData;
  sensex: IndexData;
  news: NewsItem[];
  analysis?: Analysis;
  summary?: string;
  timestamp: string;
}

export interface Holding {
  name: string;
  symbol: string;
  quantity: number;
  avgCost: number;
  ltp: number;
  pnl: number;
  returns: number;
}

export interface PortfolioData {
  totalValue: number;
  pnlToday: number;
  totalReturns: number;
  holdings: Holding[];
  allocation: { name: string; pct: number; color: string }[];
}
