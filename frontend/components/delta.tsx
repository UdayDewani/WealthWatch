import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { cn } from '@/lib/utils'

type DeltaProps = {
  value: number
  format: (v: number) => string
  className?: string
  showIcon?: boolean
  iconClassName?: string
  neutralThreshold?: number
}

/**
 * Renders a signed value with a direction arrow so P/L direction is never
 * conveyed by color alone (colorblind-safe: arrow + explicit sign).
 */
export function Delta({
  value,
  format,
  className,
  showIcon = true,
  iconClassName,
  neutralThreshold = 0,
}: DeltaProps) {
  const up = value > neutralThreshold
  const down = value < -neutralThreshold
  const tone = up
    ? 'text-positive'
    : down
      ? 'text-negative'
      : 'text-muted-foreground'

  return (
    <span
      className={cn('inline-flex items-center gap-1 font-mono tabular', tone, className)}
    >
      {showIcon &&
        (up ? (
          <ArrowUpRight className={cn('size-3.5', iconClassName)} aria-hidden="true" />
        ) : down ? (
          <ArrowDownRight className={cn('size-3.5', iconClassName)} aria-hidden="true" />
        ) : null)}
      <span>{format(value)}</span>
    </span>
  )
}
