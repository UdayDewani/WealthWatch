/**
 * Market API helpers for WealthWatch.
 * Wraps the Next.js API routes so components stay free of raw fetch() calls.
 */
import { authJson } from './client'
import { getToken } from '@/lib/session'

export type MarketOverview = {
  auth_required: boolean
  indices: Record<string, { price: number; change: number; change_pct: number } | null>
  stocks: Record<string, unknown>
  timestamp: string
  analysis?: Record<string, unknown>
  summary?: string
}

export type MarketAssetsResponse = {
  auth_required: boolean
  stocks?: Record<string, unknown>
  indices?: Record<string, unknown>
  etfs?: Record<string, unknown>
}

export type StockNewsResponse = {
  articles: Array<{
    title?: string
    headline?: string
    source: string
    time?: string
    published_at?: string | null
    url?: string
    sentiment: 'positive' | 'negative' | 'neutral'
  }>
  symbol: string
  summary: string
  available: boolean
}

export type MarketNewsResponse = {
  articles: Array<{
    title: string
    url: string
    source: string
    published_at: string | null
    sentiment: 'positive' | 'negative' | 'neutral'
  }>
  available: boolean
}

/** Fetch the full market overview (indices + summary) */
export async function getMarketOverview(): Promise<MarketOverview> {
  return authJson<MarketOverview>('/api/market/overview')
}

/** Fetch the full market assets list from the backend. */
export async function getMarketAssets(): Promise<MarketAssetsResponse> {
  return authJson<MarketAssetsResponse>('/api/markets/assets')
}

/** Fetch market-wide news headlines */
export async function getMarketNews(): Promise<MarketNewsResponse> {
  return authJson<MarketNewsResponse>('/api/news')
}

/** Fetch news articles for a specific symbol. */
export async function getStockNews(symbol: string): Promise<StockNewsResponse> {
  return authJson<StockNewsResponse>(`/api/news/${encodeURIComponent(symbol)}`)
}

/** Trigger a manual LangGraph market analysis */
export async function triggerAnalysis(): Promise<unknown> {
  return authJson('/api/market/trigger-analysis', { method: 'POST' })
}

/** Get AI analysis history */
export async function getAnalysisHistory(): Promise<unknown[]> {
  return authJson<unknown[]>('/api/market/analysis/history')
}

/**
 * Create a WebSocket connection to the live price feed.
 * Returns null when running in a non-browser context.
 * Note: WebSocket can't be proxied by Next.js rewrites — connects directly to backend.
 */
export function createWebSocket(): WebSocket | null {
  if (typeof window === 'undefined') return null
  const token = getToken()
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // Direct connection to backend (Next.js rewrites don't support WebSocket upgrade)
  const wsUrl = token
    ? `${protocol}//localhost:4040/ws?token=${encodeURIComponent(token)}`
    : `${protocol}//localhost:4040/ws`
  try {
    return new WebSocket(wsUrl)
  } catch {
    return null
  }
}
