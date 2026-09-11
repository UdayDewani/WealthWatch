'use client'

import { AlertCircle, ExternalLink, TrendingUp, Users } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { StatCard } from '@/components/stat-card'
import { Delta } from '@/components/delta'
import { formatCurrency, formatPercent } from '@/lib/format'
import { getClients, type ApiClient } from '@/lib/api/clients'
import { getMarketOverview, createWebSocket, type MarketOverview } from '@/lib/api/market'

type IndexData = {
  price: number
  change: number
  change_pct: number
} | null

export function Dashboard() {
  const [clients, setClients] = useState<ApiClient[]>([])
  const [market, setMarket] = useState<MarketOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [aiSummary, setAiSummary] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [cs, mkt] = await Promise.all([getClients(), getMarketOverview()])
        if (!cancelled) {
          setClients(cs)
          setMarket(mkt)
          // Extract AI summary from various possible locations
          const analysis = mkt.analysis as Record<string, unknown> | undefined
          if (analysis?.summary) {
            setAiSummary(String(analysis.summary))
          } else if (mkt.summary) {
            setAiSummary(mkt.summary)
          }
        }
      } catch (e) {
        console.error('Dashboard load error', e)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // WebSocket for live market updates
  useEffect(() => {
    function connect() {
      const ws = createWebSocket()
      if (!ws) return
      wsRef.current = ws
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data) as Record<string, unknown>
          setMarket((prev) => prev ? { ...prev, ...msg } as MarketOverview : msg as MarketOverview)
          if (msg.summary) setAiSummary(String(msg.summary))
          const analysis = msg.analysis as Record<string, unknown> | undefined
          if (analysis?.summary) setAiSummary(String(analysis.summary))
        } catch { /* ignore */ }
      }
      ws.onclose = () => { setTimeout(connect, 3000) }
    }
    connect()
    return () => { wsRef.current?.close() }
  }, [])

  const totalDeposited = clients.reduce((s, c) => s + (c.total_deposited ?? 0), 0)
  const totalInvested = clients.reduce((s, c) => s + (c.total_invested ?? 0), 0)
  const authRequired = market?.auth_required ?? false

  const indices = market?.indices ?? {}
  const nifty = (indices.nifty ?? indices.NIFTY_50 ?? null) as IndexData
  const sensex = (indices.sensex ?? indices.SENSEX ?? null) as IndexData

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Dashboard
          </h1>
          <p className="text-sm text-muted-foreground">
            Book overview and live market pulse
          </p>
        </div>
      </div>

      {/* Upstox connect banner */}
      {authRequired && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="size-5 shrink-0 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">
                Connect your Upstox account for live NSE data
              </p>
              <p className="text-xs text-muted-foreground">
                Nifty 50, Sensex, and stock quotes via Upstox API
              </p>
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

      {/* Live index strip */}
      {(nifty || sensex) && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {nifty && (
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Nifty 50</p>
              <p className="mt-1 font-mono text-xl font-semibold text-foreground">
                {nifty.price?.toLocaleString('en-IN')}
              </p>
              <Delta
                value={nifty.change_pct}
                format={(v) => formatPercent(v)}
                className="mt-0.5 text-xs"
              />
            </div>
          )}
          {sensex && (
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Sensex</p>
              <p className="mt-1 font-mono text-xl font-semibold text-foreground">
                {sensex.price?.toLocaleString('en-IN')}
              </p>
              <Delta
                value={sensex.change_pct}
                format={(v) => formatPercent(v)}
                className="mt-0.5 text-xs"
              />
            </div>
          )}
        </div>
      )}

      {/* AUM stats */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          label="Total AUM"
          value={formatCurrency(totalDeposited, { compact: true })}
          sub={`${clients.length} client${clients.length !== 1 ? 's' : ''}`}
        />
        <StatCard
          label="Total invested"
          value={formatCurrency(totalInvested, { compact: true })}
          sub={`${formatCurrency(totalDeposited - totalInvested, { compact: true })} in cash`}
        />
        <StatCard
          label="Deployment rate"
          value={
            totalDeposited > 0
              ? formatPercent((totalInvested / totalDeposited) * 100)
              : '—'
          }
          sub="invested vs deposited"
        />
      </div>

      {/* AI market summary */}
      {aiSummary && (
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-2 text-sm font-medium text-foreground">
            AI Market Analysis
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {aiSummary}
          </p>
        </section>
      )}

      {/* Client list */}
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium text-foreground">Clients</h2>
          <Link
            href="/manager/clients"
            className="text-xs text-primary hover:underline"
          >
            View all
          </Link>
        </div>
        {clients.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            No clients yet.{' '}
            <Link href="/manager/clients" className="text-primary hover:underline">
              Add your first client
            </Link>
            .
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[400px] text-sm">
              <thead>
                <tr className="border-b border-border/60 text-xs text-muted-foreground">
                  <th className="px-4 py-2.5 text-left font-medium">Name</th>
                  <th className="px-4 py-2.5 text-left font-medium">Risk</th>
                  <th className="px-4 py-2.5 text-right font-medium">
                    Deposited
                  </th>
                  <th className="px-4 py-2.5 text-right font-medium">
                    Invested
                  </th>
                </tr>
              </thead>
              <tbody>
                {clients.slice(0, 10).map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-border/40 last:border-0"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href="/manager/clients"
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {c.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">{c.email}</p>
                    </td>
                    <td className="px-4 py-2.5 text-xs capitalize text-muted-foreground">
                      {c.risk_profile}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular text-foreground">
                      {formatCurrency(c.total_deposited ?? 0, { compact: true })}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular text-foreground">
                      {formatCurrency(c.total_invested ?? 0, { compact: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
