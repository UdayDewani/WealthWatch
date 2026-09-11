/**
 * WealthWatch mock-data.ts
 *
 * The actual mock data arrays (instruments, clients) have been removed.
 * This file now only exports:
 *   - Type definitions (for backwards-compatibility with any remaining imports)
 *   - Math helper functions (operate on real data from the API)
 *   - A deterministic series() function (used for sparkline generation)
 *
 * Real data comes from the backend API — see lib/api/*.ts
 */

export type Point = { t: number; v: number }

export function series(seed: number, base: number, drift: number, points = 40): Point[] {
  let value = base
  const out: Point[] = []
  let s = seed
  for (let i = 0; i < points; i++) {
    s = (s * 9301 + 49297) % 233280
    const r = s / 233280 - 0.5
    value = value + r * base * 0.012 + (drift * base) / points
    out.push({ t: i, v: Math.max(value, base * 0.5) })
  }
  return out
}

export type NewsItem = {
  id: string
  headline?: string
  title?: string
  source: string
  time?: string
  published_at?: string | null
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
  pnl?: number
  pnlPct?: number
}

export type Goal = {
  id: string | number
  title: string
  target: number
  current: number
  targetDate?: string
  target_date?: string
  note: string
}

export type Client = {
  id: string | number
  name: string
  email: string
  since?: string
  joined_date?: string
  riskProfile?: 'Conservative' | 'Balanced' | 'Growth'
  risk_profile?: string
  managedBy?: string
  cash?: number
  holdings?: Holding[]
  goals?: Goal[]
  total_deposited?: number
  total_invested?: number
}

// ── Holding math helpers ──────────────────────────────────────────────────────

export function holdingValue(h: Holding) {
  return h.quantity * h.price
}
export function holdingCost(h: Holding) {
  return h.quantity * h.avgCost
}
export function holdingTotalPL(h: Holding) {
  return holdingValue(h) - holdingCost(h)
}
export function holdingTotalPLPct(h: Holding) {
  const cost = holdingCost(h)
  return cost ? (holdingTotalPL(h) / cost) * 100 : 0
}
export function holdingDayPL(h: Holding) {
  const prevPrice = h.price / (1 + h.dayChangePct / 100)
  return (h.price - prevPrice) * h.quantity
}

// ── Portfolio math helpers ────────────────────────────────────────────────────

export function portfolioValue(c: Client) {
  const cash = c.cash ?? 0
  const holdings = c.holdings ?? []
  return cash + holdings.reduce((s, h) => s + holdingValue(h), 0)
}
export function portfolioCost(c: Client) {
  return (c.holdings ?? []).reduce((s, h) => s + holdingCost(h), 0)
}
export function portfolioTotalPL(c: Client) {
  return (c.holdings ?? []).reduce((s, h) => s + holdingTotalPL(h), 0)
}
export function portfolioTotalPLPct(c: Client) {
  const cost = portfolioCost(c)
  return cost ? (portfolioTotalPL(c) / cost) * 100 : 0
}
export function portfolioDayPL(c: Client) {
  return (c.holdings ?? []).reduce((s, h) => s + holdingDayPL(h), 0)
}
export function portfolioDayPLPct(c: Client) {
  const val = (c.holdings ?? []).reduce((s, h) => s + holdingValue(h), 0)
  const day = portfolioDayPL(c)
  const prev = val - day
  return prev ? (day / prev) * 100 : 0
}

export function portfolioHistory(c: Client): Point[] {
  const end = portfolioValue(c)
  const idStr = String(c.id)
  const seed = idStr.charCodeAt(0) + (idStr.charCodeAt(1) || 0)
  const raw = series(seed, end * 0.82, 0.22, 60)
  const last = raw[raw.length - 1].v
  const factor = last > 0 ? end / last : 1
  return raw.map((p) => ({ t: p.t, v: p.v * factor }))
}

// ── Stubs (return undefined — real data comes from API) ───────────────────────

/** @deprecated Use the API layer instead — lib/api/clients.ts */
export function getClient(_id: string): Client | undefined {
  return undefined
}

/** @deprecated Use the API layer instead — lib/api/market.ts */
export function getInstrument(_symbol: string): Instrument | undefined {
  return undefined
}

/** Empty arrays — real data comes from backend API */
export const instruments: Instrument[] = []
export const clients: Client[] = []
