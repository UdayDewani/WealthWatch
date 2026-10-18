'use client';

import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Search,
  RefreshCw,
  ExternalLink,
  AlertCircle,
  TrendingUp,
  Users,
  Newspaper,
  ShieldAlert,
  HelpCircle,
} from 'lucide-react';
import { getWmStockAnalysis, StockAnalysisResponse } from '@/lib/api/wm-analysis';
import { ClientRelevanceCard } from './client-relevance-card';
import { SentimentChip } from './sentiment-chip';
import { cn } from '@/lib/utils';

type SortField = 'score' | 'name' | 'priority';
type FilterCategory = 'ALL' | 'HIGH' | 'MODERATE' | 'LOW' | 'INSUFFICIENT_DATA';

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 };

export function StockAnalysisPanel() {
  const searchParams = useSearchParams();
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<StockAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('score');
  const [filterCategory, setFilterCategory] = useState<FilterCategory>('ALL');
  const [search, setSearch] = useState('');

  const analyze = useCallback(async (sym: string) => {
    const trimmed = sym.trim().toUpperCase();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await getWmStockAnalysis(trimmed);
      setData(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Analysis failed. Please verify credentials and connectivity.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const querySymbol = searchParams.get('symbol');
    if (querySymbol) {
      const cleaned = querySymbol.toUpperCase();
      setSymbol(cleaned);
      analyze(cleaned);
    }
  }, [searchParams, analyze]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    analyze(symbol);
  };

  const clients = data?.client_analysis?.clients ?? [];
  const filtered = clients
    .filter((c) => filterCategory === 'ALL' || c.relevance_category === filterCategory)
    .filter((c) => !search || c.display_name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortField === 'score') return b.relevance_score - a.relevance_score;
      if (sortField === 'name') return a.display_name.localeCompare(b.display_name);
      if (sortField === 'priority') {
        return (PRIORITY_ORDER[a.review_priority] ?? 99) - (PRIORITY_ORDER[b.review_priority] ?? 99);
      }
      return 0;
    });

  return (
    <div className="space-y-6">
      {/* Search Header Form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="Enter stock ticker (e.g. RELIANCE, HDFCBANK, TCS)"
            className="w-full pl-9 pr-3 py-2.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary shadow-xs"
            disabled={loading}
            maxLength={30}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !symbol.trim()}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition cursor-pointer"
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>
      </form>

      {/* Error Banner */}
      {error && (
        <div className="flex items-start gap-2.5 rounded-xl border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive dark:text-red-300">
          <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="font-semibold">Analysis Request Error</p>
            <p className="text-xs leading-relaxed opacity-90">{error}</p>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="space-y-4 animate-pulse">
          <div className="h-32 rounded-xl bg-muted/60" />
          <div className="h-28 rounded-xl bg-muted/60" />
          <div className="grid gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-xl bg-muted/60" />
            ))}
          </div>
        </div>
      )}

      {/* Active Results Display */}
      {data && !loading && (
        <div className="space-y-6">
          {/* Market Intelligence Card */}
          <section className="rounded-xl border bg-card p-5 space-y-3.5 shadow-xs">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <TrendingUp className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-semibold text-lg">{data.symbol}</h2>
                    <span className="text-xs text-muted-foreground font-mono">({data.exchange})</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Market Condition & General Intelligence</p>
                </div>
              </div>
              <SentimentChip sentiment={data.market_summary.sentiment} />
            </div>

            <p className="text-sm leading-relaxed text-foreground/90 bg-muted/30 p-3.5 rounded-lg border border-border/50">
              {data.market_summary.summary}
            </p>

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground pt-1">
              {data.market_summary.cache_hit && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 px-2.5 py-0.5 font-medium">
                  ✓ Shared Redis Cache Hit
                </span>
              )}
              <span>LLM Orchestration: {data.workflow_metadata.llm_calls} call(s)</span>
              <span>
                Timestamp:{' '}
                {new Date(data.workflow_metadata.generated_at_iso).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground italic border-t border-border/40 pt-2">
              {data.market_summary.data_note}
            </p>
          </section>

          {/* Client Relevance Metric Banner */}
          <section className="rounded-xl border bg-card p-5 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                <h2 className="font-semibold text-base">Client Relevance Assessment</h2>
              </div>
              <span className="text-xs text-muted-foreground font-medium">
                {data.client_analysis.total_clients} authorized client(s) screened
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                {
                  label: 'High Relevance',
                  desc: 'Direct holding / heavy exposure',
                  value: data.client_analysis.high_relevance,
                  color: 'text-red-600 dark:text-red-400',
                  bg: 'bg-red-500/10 border-red-500/20',
                },
                {
                  label: 'Moderate',
                  desc: 'Sector / indirect link',
                  value: data.client_analysis.moderate_relevance,
                  color: 'text-amber-600 dark:text-amber-400',
                  bg: 'bg-amber-500/10 border-amber-500/20',
                },
                {
                  label: 'Low Relevance',
                  desc: 'Minimal connection',
                  value: data.client_analysis.low_relevance,
                  color: 'text-blue-600 dark:text-blue-400',
                  bg: 'bg-blue-500/10 border-blue-500/20',
                },
                {
                  label: 'Insufficient Data',
                  desc: 'No open holdings',
                  value: data.client_analysis.insufficient_data,
                  color: 'text-muted-foreground',
                  bg: 'bg-muted/40 border-border/50',
                },
              ].map((item) => (
                <div key={item.label} className={cn('rounded-xl border p-3.5 text-center', item.bg)}>
                  <p className={cn('text-2xl font-bold tracking-tight', item.color)}>{item.value}</p>
                  <p className="text-xs font-semibold mt-1">{item.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">{item.desc}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Supporting News Articles */}
          {data.news.length > 0 && (
            <section className="rounded-xl border bg-card p-5 space-y-3.5 shadow-xs">
              <div className="flex items-center gap-2">
                <Newspaper className="h-5 w-5 text-primary" />
                <h2 className="font-semibold text-base">Verified News & Material Evidence</h2>
                <span className="text-xs text-muted-foreground">({data.news.length} articles retrieved)</span>
              </div>

              <div className="grid gap-2.5">
                {data.news.map((article, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-border/60 bg-muted/20 p-3.5 hover:bg-muted/40 transition"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <a
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-semibold hover:underline text-primary flex items-center gap-1.5"
                        >
                          {article.title}
                          <ExternalLink className="h-3 w-3 shrink-0 opacity-70" />
                        </a>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                          <span className="font-medium">{article.source}</span>
                          {article.published_at && (
                            <span>• {new Date(article.published_at).toLocaleDateString()}</span>
                          )}
                          <span>•</span>
                          <span
                            className={cn(
                              'capitalize font-medium',
                              article.sentiment === 'positive' && 'text-emerald-600 dark:text-emerald-400',
                              article.sentiment === 'negative' && 'text-red-600 dark:text-red-400',
                              article.sentiment === 'neutral' && 'text-muted-foreground'
                            )}
                          >
                            {article.sentiment}
                          </span>
                        </div>
                      </div>
                    </div>
                    {article.summary && (
                      <p className="text-xs text-muted-foreground mt-2 leading-relaxed bg-background/50 p-2 rounded">
                        {article.summary}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Client Breakdown Section */}
          {clients.length > 0 && (
            <section className="space-y-3.5">
              <div className="flex items-center justify-between flex-wrap gap-2.5">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-base">Client Portfolio Explanations</h2>
                  <span className="text-xs text-muted-foreground">({filtered.length} shown)</span>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {/* Client Search */}
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search client name…"
                    className="text-xs border rounded-lg px-2.5 py-1.5 bg-background w-36 shadow-2xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {/* Category Filter */}
                  <select
                    value={filterCategory}
                    onChange={(e) => setFilterCategory(e.target.value as FilterCategory)}
                    className="text-xs border rounded-lg px-2.5 py-1.5 bg-background shadow-2xs focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="ALL">All Categories</option>
                    <option value="HIGH">High Relevance</option>
                    <option value="MODERATE">Moderate</option>
                    <option value="LOW">Low Relevance</option>
                    <option value="INSUFFICIENT_DATA">Insufficient Data</option>
                  </select>
                  {/* Sort Selection */}
                  <select
                    value={sortField}
                    onChange={(e) => setSortField(e.target.value as SortField)}
                    className="text-xs border rounded-lg px-2.5 py-1.5 bg-background shadow-2xs focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="score">Sort: Relevance Score</option>
                    <option value="priority">Sort: Review Priority</option>
                    <option value="name">Sort: Client Name</option>
                  </select>
                </div>
              </div>

              {filtered.length === 0 ? (
                <div className="rounded-xl border bg-card p-8 text-center text-muted-foreground text-sm">
                  No clients match the current search or category filter.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {filtered.map((client) => (
                    <ClientRelevanceCard key={client.client_id} client={client} />
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Empty Client Roster Warning */}
          {clients.length === 0 && (
            <div className="rounded-xl border bg-card p-8 text-center space-y-2">
              <Users className="h-8 w-8 mx-auto text-muted-foreground" />
              <p className="text-sm font-semibold">No Clients Assigned</p>
              <p className="text-xs text-muted-foreground">
                There are no active client profiles assigned to your wealth manager account yet.
              </p>
            </div>
          )}

          {/* Compliance & Methodology Footer */}
          <footer className="rounded-xl border border-border/40 bg-muted/15 p-4 text-xs text-muted-foreground space-y-1.5">
            <div className="flex items-center gap-1.5 font-medium text-foreground">
              <ShieldAlert className="h-3.5 w-3.5 text-primary" />
              <span>Compliance & Advisory Disclosure</span>
            </div>
            <p className="leading-relaxed">
              Relevance scores are generated deterministically based on verified portfolio holdings, direct allocations,
              sector exposure weights, and authorized risk profiles. This analysis is designed to assist wealth managers in
              identifying accounts requiring review; it does not constitute an automated trade recommendation or portfolio
              modification.
            </p>
          </footer>
        </div>
      )}

      {/* Initial Prompt State */}
      {!data && !loading && !error && (
        <div className="rounded-xl border border-dashed bg-card/60 p-12 text-center">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary mx-auto flex items-center justify-center mb-3.5">
            <TrendingUp className="h-6 w-6" />
          </div>
          <h3 className="font-semibold text-lg mb-1">Agentic Stock Intelligence</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
            Select any stock ticker to synthesize market condition analysis, verified news evidence, and deterministic
            relevance scoring across all authorized client portfolios.
          </p>
          <div className="flex items-center justify-center gap-2 mt-5 flex-wrap">
            <span className="text-xs text-muted-foreground mr-1">Quick Select:</span>
            {['RELIANCE', 'HDFCBANK', 'TCS', 'INFY', 'TATAMOTORS'].map((s) => (
              <button
                key={s}
                onClick={() => {
                  setSymbol(s);
                  analyze(s);
                }}
                className="px-3 py-1 text-xs font-medium rounded-full border bg-background hover:bg-muted transition cursor-pointer"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
