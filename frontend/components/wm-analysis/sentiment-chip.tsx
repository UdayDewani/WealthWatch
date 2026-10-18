import { cn } from '@/lib/utils';

const MAP: Record<string, { label: string; className: string }> = {
  bullish:  { label: '📈 Bullish',  className: 'text-green-600 dark:text-green-400' },
  positive: { label: '📈 Positive', className: 'text-green-600 dark:text-green-400' },
  bearish:  { label: '📉 Bearish',  className: 'text-red-600 dark:text-red-400' },
  negative: { label: '📉 Negative', className: 'text-red-600 dark:text-red-400' },
  neutral:  { label: '➡️ Neutral',  className: 'text-yellow-600 dark:text-yellow-400' },
};

export function SentimentChip({ sentiment }: { sentiment: string }) {
  const cfg = MAP[sentiment?.toLowerCase()] ?? MAP.neutral;
  return <span className={cn('text-sm font-medium', cfg.className)}>{cfg.label}</span>;
}
