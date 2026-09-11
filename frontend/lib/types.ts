// Shared domain types used across the WealthWatch frontend.

export type Point = { t: number; v: number }

export type NewsItem = {
  id?: string
  /** Article headline */
  headline?: string
  /** Article title (alias used by news API) */
  title?: string
  source: string
  /** Relative time string from mock data, e.g. "18m" */
  time?: string
  /** ISO timestamp from real API */
  published_at?: string | null

  /** URL to the full article */
  url?: string
  sentiment: 'positive' | 'negative' | 'neutral'
}

export type Instrument = {
  symbol: string
  name: string
  sector: string
  currency: string
  price: number
  change: number
  changePct: number
  dayHigh: number
  dayLow: number
  marketCap: number
  volume: number
  spark: Point[]
  newsSummary: string
  news: NewsItem[]
}

export type Holding = {
  symbol: string
  name: string
  quantity: number
  avgCost: number
  price: number
  dayChangePct: number
  /** Pre-computed P/L from the API (optional — HoldingsTable falls back to price-based calc) */
  pnl?: number
  pnlPct?: number
}

/** Generates a deterministic 60-point portfolio-value history ending at `currentValue`. */
export function generatePortfolioHistory(currentValue: number, seed: number): Point[] {
  let value = currentValue * 0.82
  const base = currentValue * 0.82
  const points = 60
  const out: Point[] = []
  let s = seed
  for (let i = 0; i < points; i++) {
    s = (s * 9301 + 49297) % 233280
    const r = s / 233280 - 0.5
    value = value + r * base * 0.012 + (0.22 * base) / points
    out.push({ t: i, v: Math.max(value, base * 0.5) })
  }
  // Normalize so the last point equals currentValue
  const last = out[out.length - 1].v
  const factor = currentValue / last
  return out.map((p) => ({ t: p.t, v: p.v * factor }))
}
