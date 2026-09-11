'use client'

import { useEffect, useState } from 'react'
import { Delta } from '@/components/delta'
import { HoldingsTable } from '@/components/holdings-table'
import { StatCard } from '@/components/stat-card'
import { ValueChart } from '@/components/value-chart'
import {
  formatCurrency,
  formatPercent,
  formatSignedCurrency,
} from '@/lib/format'
import { getMyPortfolio, type Portfolio, type Investment } from '@/lib/api/portfolio'
import { generatePortfolioHistory } from '@/lib/types'
import type { Holding } from '@/lib/types'
import { readSession } from '@/lib/session'

const ranges = [
  { label: '3M', points: 20 },
  { label: '6M', points: 40 },
  { label: '1Y', points: 60 },
]

function investmentsToHoldings(investments: Investment[]): Holding[] {
  return investments.map((inv) => ({
    symbol: inv.symbol,
    name: inv.asset_name,
    quantity: inv.quantity,
    avgCost: inv.buy_price,
    price: inv.current_price ?? inv.buy_price,
    dayChangePct: 0,
    pnl: inv.pnl,
    pnlPct: inv.pnl_pct,
  }))
}

export function ClientPortfolio() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [loading, setLoading] = useState(true)
  const [range, setRange] = useState('1Y')
  const session = readSession()
  const clientName = session?.name ?? 'Client'

  useEffect(() => {
    let cancelled = false
    getMyPortfolio()
      .then((p) => { if (!cancelled) setPortfolio(p) })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
      </div>
    )
  }

  if (!portfolio) {
    return (
      <div className="mx-auto max-w-4xl py-16 text-center text-sm text-muted-foreground">
        Failed to load portfolio. Please try again.
      </div>
    )
  }

  const value = portfolio.current_value + portfolio.available_cash
  const unrealizedPnl = portfolio.unrealized_pnl
  const realizedPnl = portfolio.realized_pnl
  const totalPnl = unrealizedPnl + realizedPnl
  const totalInvested = portfolio.total_invested
  const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0
  const holdings = investmentsToHoldings(portfolio.open_investments)

  // Generate portfolio history chart data (deterministic until real history is available)
  const seed = clientName.charCodeAt(0) + (clientName.charCodeAt(1) || 0)
  const fullHistory = generatePortfolioHistory(value, seed)
  const points = ranges.find((r) => r.label === range)?.points ?? 60
  const history = fullHistory.slice(-points)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-sm text-muted-foreground">
          Welcome back, {clientName.split(' ')[0]}
        </p>
        <h1 className="text-pretty text-2xl font-semibold tracking-tight text-foreground">
          Your portfolio is worth{' '}
          <span className="font-mono tabular">
            {formatCurrency(value, { decimals: 0 })}
          </span>
        </h1>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          label="Total value"
          value={formatCurrency(value, { decimals: 0 })}
          sub={`${formatCurrency(portfolio.available_cash, { compact: true })} in cash`}
        />
        <StatCard
          label="Unrealized P/L"
          value={formatSignedCurrency(unrealizedPnl)}
          delta={totalPnlPct}
          deltaFormat={(v) => formatPercent(v)}
        />
        <StatCard
          label="Realized P/L"
          value={formatSignedCurrency(realizedPnl)}
        />
      </div>

      <section className="rounded-xl border border-border bg-card p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex flex-col">
            <h2 className="text-sm font-medium text-foreground">
              Value over time
            </h2>
            <Delta
              value={totalPnl}
              format={() =>
                `${formatSignedCurrency(totalPnl)} · ${formatPercent(totalPnlPct)}`
              }
              className="mt-0.5 text-xs"
            />
          </div>
          <div className="flex items-center gap-1">
            {ranges.map((r) => (
              <button
                key={r.label}
                type="button"
                onClick={() => setRange(r.label)}
                className={`rounded px-2 py-0.5 font-mono text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  range === r.label
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <ValueChart
          key={range}
          data={history}
          tone={totalPnl >= 0 ? 'positive' : 'negative'}
          height={220}
          formatValue={(v) => formatCurrency(v, { decimals: 0 })}
        />
      </section>

      {holdings.length > 0 && (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-foreground">Your holdings</h2>
          <HoldingsTable holdings={holdings} />
        </div>
      )}

      {holdings.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
          No open investments yet. Your advisor will add holdings to your portfolio.
        </div>
      )}
    </div>
  )
}
