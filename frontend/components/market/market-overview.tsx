'use client'

import { AlertCircle, ExternalLink, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Delta } from '@/components/delta'
import { Sparkline } from '@/components/sparkline'
import { InstrumentDetail } from '@/components/market/instrument-detail'
import { formatNumber, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'
import { getMarketAssets, createWebSocket } from '@/lib/api/market'
import type { Instrument, Point } from '@/lib/types'

type LiveQuote = {
  price: number
  change: number
  changePct: number
  prevClose: number
  flash: 'up' | 'down' | null
}

function generateSpark(seed: number, base: number): Point[] {
  let s = seed
  let v = base
  const out: Point[] = []
  for (let i = 0; i < 40; i++) {
    s = (s * 9301 + 49297) % 233280
    const r = s / 233280 - 0.5
    v = Math.max(v + r * base * 0.012, base * 0.5)
    out.push({ t: i, v })
  }
  return out
}

function apiToInstrument(sym: string, data: Record<string, unknown>): Instrument {
  const price = Number(data.price ?? data.last_price ?? 0)
  const change = Number(data.change ?? 0)
  const changePct = Number(data.change_pct ?? data.changePct ?? 0)
  const seed = sym.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return {
    symbol: sym,
    name: String(data.name ?? data.asset_name ?? sym),
    sector: String(data.sector ?? data.asset_type ?? 'Equity'),
    currency: String(data.currency ?? 'INR'),
    price,
    change,
    changePct,
    dayHigh: Number(data.day_high ?? data.dayHigh ?? price * 1.01),
    dayLow: Number(data.day_low ?? data.dayLow ?? price * 0.99),
    marketCap: Number(data.market_cap ?? data.marketCap ?? 0),
    volume: Number(data.volume ?? 0),
    spark: generateSpark(seed, price || 100),
    newsSummary: '',
    news: [],
  }
}

export function MarketOverview() {
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [live, setLive] = useState<Record<string, LiveQuote>>({})
  const [selected, setSelected] = useState<string>('')
  const [query, setQuery] = useState('')
  const [sector, setSector] = useState('All')
  const [authRequired, setAuthRequired] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const now = useNow()

  // Load market assets
  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getMarketAssets()
        if (cancelled) return
        setAuthRequired(data.auth_required)
        if (data.auth_required) {
          setLoading(false)
          return
        }
        // Flatten all instrument types into one list
        const all: Instrument[] = []
        const sources = [
          ['stocks', data.stocks ?? {}],
          ['indices', data.indices ?? {}],
          ['etfs', data.etfs ?? {}],
        ] as [string, Record<string, unknown>][]
        for (const [, group] of sources) {
          for (const [sym, d] of Object.entries(group)) {
            if (d && typeof d === 'object') {
              all.push(apiToInstrument(sym, d as Record<string, unknown>))
            }
          }
        }
        if (all.length > 0) {
          setInstruments(all)
          setSelected(all[0].symbol)
          const initLive: Record<string, LiveQuote> = {}
          for (const i of all) {
            initLive[i.symbol] = {
              price: i.price,
              change: i.change,
              changePct: i.changePct,
              prevClose: i.price - i.change,
              flash: null,
            }
          }
          setLive(initLive)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load market data')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // WebSocket live updates
  useEffect(() => {
    const ws = createWebSocket()
    if (!ws) return
    wsRef.current = ws
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.stocks && typeof msg.stocks === 'object') {
          setLive((prev) => {
            const next = { ...prev }
            for (const [sym, d] of Object.entries(msg.stocks as Record<string, unknown>)) {
              if (d && typeof d === 'object') {
                const data = d as Record<string, unknown>
                const price = Number(data.price ?? 0)
                const change = Number(data.change ?? 0)
                const prevClose = price - change
                const changePct = prevClose ? (change / prevClose) * 100 : 0
                const prev_price = prev[sym]?.price ?? price
                next[sym] = { price, change, changePct, prevClose, flash: price > prev_price ? 'up' : price < prev_price ? 'down' : null }
              }
            }
            return next
          })
        }
      } catch { /* ignore */ }
    }
    ws.onclose = () => {
      setTimeout(() => {
        const newWs = createWebSocket()
        if (newWs) wsRef.current = newWs
      }, 3000)
    }
    return () => ws.close()
  }, [])

  const sectors = useMemo(
    () => ['All', ...Array.from(new Set(instruments.map((i) => i.sector)))],
    [instruments],
  )

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return instruments.filter((i) => {
      const matchesQuery = !q || i.symbol.toLowerCase().includes(q) || i.name.toLowerCase().includes(q)
      const matchesSector = sector === 'All' || i.sector === sector
      return matchesQuery && matchesSector
    })
  }, [query, sector, instruments])

  const selectedInst = instruments.find((i) => i.symbol === selected) ?? null

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Market Overview</h1>
          <span className="inline-flex items-center gap-2 font-mono text-xs text-muted-foreground">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-positive/60" />
              <span className="relative inline-flex size-1.5 rounded-full bg-positive" />
            </span>
            LIVE · {now}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          Real-time pricing across the coverage list. Select an instrument for news and history.
        </p>
      </div>

      {/* Upstox connect banner */}
      {authRequired && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="size-5 shrink-0 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">Connect your Upstox account</p>
              <p className="text-xs text-muted-foreground">Link Upstox to see live NSE market data — Nifty 50, Sensex, stocks, and ETFs.</p>
            </div>
          </div>
          <a
            href="http://localhost:4040/auth"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Connect Upstox
            <ExternalLink className="size-3.5" />
          </a>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-20">
          <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
        </div>
      )}

      {!loading && !authRequired && instruments.length === 0 && (
        <div className="rounded-xl border border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
          No market data available. Connect your Upstox account to see live instruments.
        </div>
      )}

      {!loading && instruments.length > 0 && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_380px]">
          {/* Price table */}
          <section className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="flex flex-col gap-3 border-b border-border p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative w-full sm:max-w-56">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search symbol or name"
                  aria-label="Search instruments"
                  className="h-8 w-full rounded-md border border-input bg-surface pl-8 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                />
              </div>
              <div className="flex items-center gap-1 overflow-x-auto">
                {sectors.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSector(s)}
                    className={cn(
                      'shrink-0 rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      sector === s ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[540px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th className="px-4 py-2 text-left font-medium">Instrument</th>
                    <th className="px-3 py-2 text-right font-medium">Last</th>
                    <th className="px-3 py-2 text-right font-medium">Chg</th>
                    <th className="px-3 py-2 text-right font-medium">% Chg</th>
                    <th className="px-4 py-2 text-right font-medium">1D Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((i) => {
                    const l = live[i.symbol] ?? { price: i.price, change: i.change, changePct: i.changePct, flash: null }
                    const isSel = selected === i.symbol
                    return (
                      <tr
                        key={i.symbol}
                        onClick={() => setSelected(i.symbol)}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(i.symbol) } }}
                        aria-selected={isSel}
                        className={cn(
                          'group relative cursor-pointer border-b border-border/60 outline-none transition-colors last:border-0 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                          isSel ? 'bg-accent/50' : 'hover:bg-surface',
                        )}
                      >
                        <td className="relative px-4 py-2.5">
                          {isSel && <span className="absolute inset-y-0 left-0 w-0.5 bg-primary" />}
                          <div className="flex flex-col">
                            <span className="font-mono text-sm font-medium text-foreground">{i.symbol}</span>
                            <span className="max-w-40 truncate text-xs text-muted-foreground">{i.name}</span>
                          </div>
                        </td>
                        <td className={cn('rounded px-3 py-2.5 text-right font-mono tabular text-foreground transition-colors duration-500', l.flash === 'up' && 'bg-green-50 dark:bg-green-950/20', l.flash === 'down' && 'bg-red-50 dark:bg-red-950/20')}>
                          {formatNumber(l.price)}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <Delta value={l.change} format={(v) => formatNumber(v)} showIcon={false} className="justify-end text-[13px]" />
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <Delta value={l.changePct} format={(v) => formatPercent(v)} className="justify-end text-[13px]" />
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex justify-end">
                            <Sparkline data={i.spark} positive={l.changePct >= 0} />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-10 text-center text-sm text-muted-foreground">
                        No instruments match &ldquo;{query}&rdquo;.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* Detail panel */}
          <div className="lg:sticky lg:top-20 lg:self-start">
            {selectedInst ? (
              <InstrumentDetail symbol={selected} live={live[selected] ?? null} instrument={selectedInst} />
            ) : (
              <div className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
                Select an instrument to see details.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function useNow() {
  const [now, setNow] = useState('')
  useEffect(() => {
    function tick() {
      setNow(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return now
}
