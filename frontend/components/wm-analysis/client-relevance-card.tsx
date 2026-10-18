'use client';
import { useState } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle, Info, BarChart3 } from 'lucide-react';
import { ClientRelevance } from '@/lib/api/wm-analysis';
import { RelevanceBadge, PriorityLabel } from './relevance-badge';
import { formatCurrency, formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';

interface Props {
  client: ClientRelevance;
}

export function ClientRelevanceCard({ client }: Props) {
  const [expanded, setExpanded] = useState(false);

  const scoreColor = client.relevance_score >= 40
    ? 'bg-red-500'
    : client.relevance_score >= 20
    ? 'bg-yellow-500'
    : 'bg-blue-400';

  return (
    <div className={cn(
      'rounded-xl border bg-card shadow-sm transition-all',
      client.relevance_category === 'HIGH' && 'border-red-200 dark:border-red-800',
      client.relevance_category === 'MODERATE' && 'border-yellow-200 dark:border-yellow-800',
      client.relevance_category === 'LOW' && 'border-blue-200 dark:border-blue-800',
      client.relevance_category === 'INSUFFICIENT_DATA' && 'border-gray-200 dark:border-gray-700 opacity-70',
    )}>
      {/* Header */}
      <button
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Score circle */}
          <div className="flex flex-col items-center">
            <div className="w-10 h-10 rounded-full flex items-center justify-center border-2 border-muted bg-background">
              <span className="text-sm font-bold">{client.relevance_score}</span>
            </div>
            <div className="w-10 h-1 rounded mt-1 bg-muted">
              <div
                className={cn('h-full rounded', scoreColor)}
                style={{ width: `${client.relevance_score}%` }}
              />
            </div>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-sm truncate">{client.display_name}</span>
              <RelevanceBadge category={client.relevance_category} />
            </div>
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              <PriorityLabel priority={client.review_priority} />
              <span className="text-xs text-muted-foreground capitalize">· {client.risk_profile} risk</span>
              {client.existing_exposure.held && (
                <span className="text-xs text-green-600 dark:text-green-400">
                  · Holds {formatNumber(client.existing_exposure.quantity)} units
                </span>
              )}
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 shrink-0" /> : <ChevronDown className="h-4 w-4 shrink-0" />}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t pt-3">
          {/* Exposure summary */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="rounded-lg bg-muted/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Portfolio Value</p>
              <p className="text-sm font-semibold">{formatCurrency(client.portfolio_value)}</p>
            </div>
            {client.existing_exposure.held && (
              <div className="rounded-lg bg-muted/50 p-2 text-center">
                <p className="text-xs text-muted-foreground">Direct Allocation</p>
                <p className="text-sm font-semibold">{client.existing_exposure.current_allocation_pct.toFixed(1)}%</p>
              </div>
            )}
            {client.target_sector_pct > 0 && (
              <div className="rounded-lg bg-muted/50 p-2 text-center">
                <p className="text-xs text-muted-foreground">Sector Exposure</p>
                <p className="text-sm font-semibold">{client.target_sector_pct.toFixed(1)}%</p>
              </div>
            )}
          </div>

          {/* Sector breakdown */}
          {Object.keys(client.sector_exposure).length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
                <BarChart3 className="h-3 w-3" /> Sector Allocation
              </p>
              <div className="flex flex-wrap gap-1">
                {Object.entries(client.sector_exposure)
                  .sort(([, a], [, b]) => b - a)
                  .map(([sector, pct]) => (
                    <span key={sector} className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs bg-muted">
                      {sector} <strong>{pct.toFixed(1)}%</strong>
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* AI explanation */}
          <div className="rounded-lg bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
              <Info className="h-3 w-3" /> Assessment
            </p>
            <p className="text-sm leading-relaxed">{client.explanation}</p>
          </div>

          {/* Key risks */}
          {client.key_risks.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" /> Key Risks
              </p>
              <ul className="space-y-1">
                {client.key_risks.map((risk, i) => (
                  <li key={i} className="text-xs text-muted-foreground flex items-start gap-1">
                    <span className="text-red-400 mt-0.5">•</span> {risk}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Evidence */}
          {client.evidence.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Evidence</p>
              <ul className="space-y-1">
                {client.evidence.map((ev, i) => (
                  <li key={i} className="text-xs text-blue-600 dark:text-blue-400">{ev}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Score breakdown */}
          {Object.keys(client.score_breakdown).length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Score breakdown</summary>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(client.score_breakdown).map(([k, v]) => (
                  <span key={k} className="rounded bg-muted px-1.5 py-0.5">
                    {k.replace(/_/g, ' ')}: +{v}
                  </span>
                ))}
              </div>
            </details>
          )}

          {/* Data quality */}
          {client.data_quality !== 'complete' && (
            <p className="text-xs text-muted-foreground italic">
              Data quality: {client.data_quality} — assessment may be incomplete.
            </p>
          )}

          {/* Disclaimer */}
          <p className="text-xs text-muted-foreground border-t pt-2">{client.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
