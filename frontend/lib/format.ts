export function formatCurrency(
  value: number,
  opts: { compact?: boolean; currency?: string; decimals?: number } = {},
) {
  const { compact = false, currency = 'USD', decimals } = opts
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    notation: compact ? 'compact' : 'standard',
    minimumFractionDigits: decimals ?? (compact ? 0 : 2),
    maximumFractionDigits: decimals ?? (compact ? 1 : 2),
  }).format(value)
}

export function formatNumber(value: number, decimals = 2) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

export function formatPercent(value: number, withSign = true) {
  const sign = withSign && value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

export function formatSignedCurrency(value: number, opts?: { compact?: boolean; currency?: string; decimals?: number }): string {
  const prefix = value >= 0 ? '+' : ''
  return prefix + formatCurrency(value, opts)
}
