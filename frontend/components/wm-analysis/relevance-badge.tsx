import { cn } from '@/lib/utils';

type Category = 'HIGH' | 'MODERATE' | 'LOW' | 'INSUFFICIENT_DATA';

const CONFIG: Record<Category, { label: string; className: string }> = {
  HIGH: { label: 'High Relevance', className: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' },
  MODERATE: { label: 'Moderate', className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' },
  LOW: { label: 'Low Relevance', className: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' },
  INSUFFICIENT_DATA: { label: 'Insufficient Data', className: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
};

export function RelevanceBadge({ category }: { category: Category }) {
  const cfg = CONFIG[category] ?? CONFIG.INSUFFICIENT_DATA;
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', cfg.className)}>
      {cfg.label}
    </span>
  );
}

const PRIORITY_CONFIG: Record<string, { label: string; className: string }> = {
  urgent: { label: '🔴 Urgent Review', className: 'text-red-600 dark:text-red-400' },
  high: { label: '🟠 High Priority', className: 'text-orange-600 dark:text-orange-400' },
  normal: { label: '🟡 Normal Priority', className: 'text-yellow-600 dark:text-yellow-400' },
  low: { label: '⚪ Low Priority', className: 'text-gray-500 dark:text-gray-400' },
};

export function PriorityLabel({ priority }: { priority: string }) {
  const cfg = PRIORITY_CONFIG[priority] ?? PRIORITY_CONFIG.low;
  return <span className={cn('text-xs font-medium', cfg.className)}>{cfg.label}</span>;
}
