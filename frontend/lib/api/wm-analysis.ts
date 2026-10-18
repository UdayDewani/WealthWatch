import { authJson } from './client';

export interface StockAnalysisMarketSummary {
  summary: string;
  sentiment: string;
  generated_at: number | null;
  analysis_version: string | null;
  cache_hit: boolean;
  data_note: string;
}

export interface StockAnalysisArticle {
  title: string;
  source: string;
  url: string;
  published_at: string | null;
  sentiment: string;
  summary: string;
  relevance_note: string;
}

export interface ClientRelevance {
  client_id: number;
  display_name: string;
  risk_profile: string;
  relevance_category: 'HIGH' | 'MODERATE' | 'LOW' | 'INSUFFICIENT_DATA';
  relevance_score: number;
  score_breakdown: Record<string, number>;
  score_explanation: string;
  existing_exposure: {
    held: boolean;
    quantity: number;
    avg_buy_price: number;
    current_allocation_pct: number;
  };
  portfolio_value: number;
  sector_exposure: Record<string, number>;
  target_sector_pct: number;
  explanation: string;
  key_risks: string[];
  review_priority: 'urgent' | 'high' | 'normal' | 'low';
  evidence: string[];
  data_quality: 'complete' | 'partial' | 'minimal';
  disclaimer: string;
}

export interface StockAnalysisResponse {
  symbol: string;
  exchange: string;
  market_summary: StockAnalysisMarketSummary;
  news: StockAnalysisArticle[];
  client_analysis: {
    total_clients: number;
    high_relevance: number;
    moderate_relevance: number;
    low_relevance: number;
    insufficient_data: number;
    clients: ClientRelevance[];
  };
  workflow_metadata: {
    generated_at: number;
    generated_at_iso: string;
    market_cache_hit: boolean;
    llm_calls: number;
    total_clients_assessed: number;
  };
}

export async function getWmStockAnalysis(
  symbol: string,
  exchange = 'NSE'
): Promise<StockAnalysisResponse> {
  const params = new URLSearchParams({ exchange });
  return authJson<StockAnalysisResponse>(
    `/api/wm/stock-analysis/${encodeURIComponent(symbol.toUpperCase())}?${params}`
  );
}
