import { cn } from '@/lib/utils'

export function Wordmark({
  className,
  showText = true,
}: {
  className?: string
  showText?: boolean
}) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span
        aria-hidden="true"
        className="grid size-7 place-items-center rounded-[7px] bg-primary text-primary-foreground"
      >
        {/* concentric mark: a watched, measured position */}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="1.5" y="1.5" width="13" height="13" rx="3" stroke="currentColor" strokeWidth="1.4" opacity="0.5" />
          <path d="M4 10.5L6.5 7.5L9 9.5L12 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      {showText && (
        <span className="text-[15px] font-semibold tracking-tight text-foreground">
          Wealth<span className="text-muted-foreground">Watch</span>
        </span>
      )}
    </span>
  )
}
