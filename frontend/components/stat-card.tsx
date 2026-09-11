import { Delta } from '@/components/delta'
import { cn } from '@/lib/utils'

export function StatCard({
  label,
  value,
  delta,
  deltaFormat,
  sub,
  emphasis = false,
  className,
}: {
  label: string
  value: string
  delta?: number
  deltaFormat?: (v: number) => string
  sub?: string
  emphasis?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 rounded-xl border border-border bg-card p-4',
        emphasis && 'bg-surface',
        className,
      )}
    >
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="font-mono text-2xl font-semibold tabular tracking-tight text-foreground">
        {value}
      </span>
      <div className="flex items-center gap-2 text-sm">
        {delta !== undefined && deltaFormat && (
          <Delta value={delta} format={deltaFormat} className="text-[13px]" />
        )}
        {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
      </div>
    </div>
  )
}
