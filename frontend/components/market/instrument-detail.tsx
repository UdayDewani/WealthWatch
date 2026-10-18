'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Sparkles } from 'lucide-react'
import { Delta } from '@/components/delta'
import { ValueChart } from '@/components/value-chart'
import { formatNumber, formatPercent, formatCurrency } from '@/lib/format'
import { getStockNews } from '@/lib/api/market'
import type { Instrument, NewsItem } from '@/lib/types'

type Live = {
  price: number
  change: number
  changePct: number
} | null

const ranges = [
  { label: '1D', points: 12 },
  { label: '1W', points: 20 },
  { label: '1M', points: 40 },
]

const sentimentTone: Record<string, string> = {
  positive: 'bg-green-500',
  negative: 'bg-red-500',
  neutral: 'bg-muted-foreground',
}

export function InstrumentDetail({
  symbol,
  live,
  instrument,
}: {
  symbol: string
  live: Live
  instrument: Instrument
}) {
  const [range, setRange] = useState('1M')
  const [news, setNews] = useState<NewsItem[]>(instrument.news ?? [])
  const [newsSummary, setNewsSummary] = useState(instrument.newsSummary ?? '')
  const [newsLoading, setNewsLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setNewsLoading(true)
    setNews([])
    setNewsSummary('')
    getStockNews(symbol)
      .then((data) => {
        if (!cancelled) {
          setNews(data.articles)
          setNewsSummary(data.summary)
        }
      })
      .catch(() => { /* leave empty */ })
      .finally(() => { if (!cancelled) setNewsLoading(false) })
    return () => { cancelled = true }
  }, [symbol])

  const inst = instrument
  const price = live?.price ?? inst.price
  const changePct = live?.changePct ?? inst.changePct
  const change = live?.change ?? inst.change
  const positive = changePct >= 0

  const points = ranges.find((r) => r.label === range)?.points ?? 40
  const chartData = inst.spark.slice(-points).map((p, i) => ({ t: i, v: p.v }))

  const stats: { label: string; value: string }[] = [
    { label: 'Day range', value: inst.dayHigh && inst.dayLow ? `${formatNumber(inst.dayLow)} – ${formatNumber(inst.dayHigh)}` : '—' },
    { label: 'Volume', value: inst.volume ? formatNumber(inst.volume, 0) : '—' },
    { label: 'Mkt cap', value: inst.marketCap ? formatCurrency(inst.marketCap, { compact: true, decimals: 1 }) : '—' },
    { label: 'Sector', value: inst.sector },
  ]

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-semibold tracking-tight text-foreground">{inst.symbol}</span>
            <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-border">{inst.currency}</span>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">{inst.name}</p>
        </div>
        <Link
          href={`/manager/stock-analysis?symbol=${encodeURIComponent(inst.symbol)}`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-primary/20 bg-primary/10 hover:bg-primary/15 text-primary px-3 py-1.5 text-xs font-medium transition shadow-2xs"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>Analyze for Clients</span>
        </Link>
      </div>

      <div className="flex items-end justify-between">
        <span className="font-mono text-3xl font-semibold tabular tracking-tight text-foreground">{formatNumber(price)}</span>
        <div className="flex flex-col items-end gap-0.5 text-sm">
          <Delta value={change} format={(v) => formatNumber(v)} />
          <Delta value={changePct} format={(v) => formatPercent(v)} showIcon={false} />
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-end gap-1">
          {ranges.map((r) => (
            <button
              key={r.label}
              type="button"
              onClick={() => setRange(r.label)}
              className={`rounded px-2 py-0.5 font-mono text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                range === r.label ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <ValueChart
          key={`${symbol}-${range}`}
          data={chartData}
          tone={positive ? 'positive' : 'negative'}
          height={140}
          formatValue={(v) => formatNumber(v)}
        />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-y border-border py-4">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col gap-0.5">
            <dt className="text-xs text-muted-foreground">{s.label}</dt>
            <dd className="font-mono text-sm tabular text-foreground">{s.value}</dd>
          </div>
        ))}
      </dl>

      {newsSummary && (
        <div>
          <h3 className="text-sm font-medium text-foreground">News summary</h3>
          <p className="mt-1.5 text-pretty text-sm leading-relaxed text-muted-foreground">{newsSummary}</p>
        </div>
      )}

      <div>
        <h3 className="mb-1.5 text-sm font-medium text-foreground">Latest headlines</h3>
        {newsLoading && (
          <p className="text-xs text-muted-foreground">Loading news…</p>
        )}
        {!newsLoading && news.length === 0 && (
          <p className="text-xs text-muted-foreground">No recent news available for this instrument.</p>
        )}
        <ul className="flex flex-col">
          {news.map((n, idx) => (
            <li key={n.url ?? idx} className="flex items-start gap-2.5 border-t border-border/60 py-2.5 first:border-t-0">
              <span
                className={`mt-1.5 size-1.5 shrink-0 rounded-full ${sentimentTone[n.sentiment] ?? 'bg-muted-foreground'}`}
                aria-hidden="true"
              />
              <div className="min-w-0">
                {n.url ? (
                  <a
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-pretty text-sm leading-snug text-foreground hover:underline"
                  >
                    {n.title ?? n.headline}
                  </a>
                ) : (
                  <p className="text-pretty text-sm leading-snug text-foreground">{n.title ?? n.headline}</p>
                )}
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {n.source}{n.published_at ? ` · ${new Date(n.published_at).toLocaleDateString()}` : n.time ? ` · ${n.time} ago` : ''}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

