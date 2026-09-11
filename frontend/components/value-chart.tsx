'use client'

import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts'
import type { Point } from '@/lib/mock-data'

type Tone = 'accent' | 'positive' | 'negative'

const toneVar: Record<Tone, string> = {
  accent: 'var(--primary)',
  positive: 'var(--positive)',
  negative: 'var(--negative)',
}

export function ValueChart({
  data,
  tone = 'accent',
  height = 220,
  formatValue,
  showTooltip = true,
}: {
  data: Point[]
  tone?: Tone
  height?: number
  formatValue?: (v: number) => string
  showTooltip?: boolean
}) {
  const color = toneVar[tone]
  const id = `grad-${tone}`
  const values = data.map((d) => d.v)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = (max - min) * 0.12 || 1

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.22} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={[min - pad, max + pad]} />
        {showTooltip && (
          <Tooltip
            cursor={{ stroke: 'var(--border)', strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const v = payload[0].value as number
              return (
                <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-sm">
                  <span className="font-mono tabular text-popover-foreground">
                    {formatValue ? formatValue(v) : v.toFixed(2)}
                  </span>
                </div>
              )
            }}
          />
        )}
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={2}
          fill={`url(#${id})`}
          dot={false}
          activeDot={{ r: 3, strokeWidth: 0, fill: color }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
