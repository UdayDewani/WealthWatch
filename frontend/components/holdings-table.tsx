import { Delta } from '@/components/delta'
import { formatCurrency, formatNumber, formatPercent } from '@/lib/format'
import { type Holding } from '@/lib/types'
import {
  holdingTotalPL,
  holdingTotalPLPct,
  holdingValue,
} from '@/lib/mock-data'

export function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const total = holdings.reduce((s, h) => s + holdingValue(h), 0)

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full min-w-[620px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground">
            <th className="px-4 py-2.5 text-left font-medium">Holding</th>
            <th className="px-3 py-2.5 text-right font-medium">Qty</th>
            <th className="px-3 py-2.5 text-right font-medium">Avg cost</th>
            <th className="px-3 py-2.5 text-right font-medium">Last</th>
            <th className="px-3 py-2.5 text-right font-medium">Value</th>
            <th className="px-3 py-2.5 text-right font-medium">Day</th>
            <th className="px-4 py-2.5 text-right font-medium">Total P/L</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const value = holdingValue(h)
            const weight = total ? (value / total) * 100 : 0
            return (
              <tr
                key={h.symbol}
                className="border-b border-border/60 last:border-0"
              >
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-sm font-medium text-foreground">
                        {h.symbol}
                      </span>
                      <span className="max-w-36 truncate text-xs text-muted-foreground">
                        {h.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="h-1 w-24 overflow-hidden rounded-full bg-muted">
                        <span
                          className="block h-full rounded-full bg-primary/70"
                          style={{ width: `${Math.min(weight, 100)}%` }}
                        />
                      </span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {weight.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3 text-right font-mono tabular text-foreground">
                  {formatNumber(h.quantity, 0)}
                </td>
                <td className="px-3 py-3 text-right font-mono tabular text-muted-foreground">
                  {formatNumber(h.avgCost)}
                </td>
                <td className="px-3 py-3 text-right font-mono tabular text-foreground">
                  {formatNumber(h.price)}
                </td>
                <td className="px-3 py-3 text-right font-mono tabular text-foreground">
                  {formatCurrency(value, { decimals: 0 })}
                </td>
                <td className="px-3 py-3 text-right">
                  <Delta
                    value={h.dayChangePct}
                    format={(v) => formatPercent(v)}
                    className="justify-end text-[13px]"
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex flex-col items-end">
                    <Delta
                      value={holdingTotalPL(h)}
                      format={(v) => formatCurrency(v, { decimals: 0 })}
                      showIcon={false}
                      className="text-[13px]"
                    />
                    <Delta
                      value={holdingTotalPLPct(h)}
                      format={(v) => formatPercent(v)}
                      showIcon={false}
                      className="text-[11px]"
                    />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
