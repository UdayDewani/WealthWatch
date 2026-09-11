'use client'

import { FileText, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Delta } from '@/components/delta'
import { HoldingsTable } from '@/components/holdings-table'
import { ReportDialog } from '@/components/report-dialog'
import { StatCard } from '@/components/stat-card'
import { ValueChart } from '@/components/value-chart'
import { formatCurrency, formatPercent, formatSignedCurrency } from '@/lib/format'
import { type ApiClient } from '@/lib/api/clients'
import { getClientPortfolio, addDeposit, addInvestment, type Portfolio, type Investment } from '@/lib/api/portfolio'
import { getGoals, createGoal, deleteGoal, type Goal } from '@/lib/api/goals'
import { generatePortfolioHistory } from '@/lib/types'
import type { Holding } from '@/lib/types'

function normaliseRisk(raw: string): 'Conservative' | 'Balanced' | 'Growth' {
  const r = raw?.toLowerCase()
  if (r === 'conservative') return 'Conservative'
  if (r === 'growth' || r === 'aggressive') return 'Growth'
  return 'Balanced'
}

const riskTone: Record<string, string> = {
  Conservative: 'text-primary ring-primary/20 bg-primary/10',
  Balanced: 'text-accent-foreground ring-border bg-accent',
  Growth: 'text-green-700 dark:text-green-400 ring-green-200 dark:ring-green-900 bg-green-50 dark:bg-green-950/30',
}

function investmentsToHoldings(investments: Investment[]): Holding[] {
  return investments.map((inv) => ({
    symbol: inv.symbol,
    name: inv.asset_name,
    quantity: inv.quantity,
    avgCost: inv.buy_price,
    price: inv.current_price ?? inv.buy_price,
    dayChangePct: 0,
    pnl: inv.pnl,
    pnlPct: inv.pnl_pct,
  }))
}

export function ClientDetail({ client, onRefresh }: { client: ApiClient; onRefresh?: () => void }) {
  const [reportOpen, setReportOpen] = useState(false)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)

  // Deposit form
  const [showDeposit, setShowDeposit] = useState(false)
  const [depositAmount, setDepositAmount] = useState('')
  const [depositNote, setDepositNote] = useState('')
  const [depositLoading, setDepositLoading] = useState(false)

  // Investment form
  const [showInvest, setShowInvest] = useState(false)
  const [invSymbol, setInvSymbol] = useState('')
  const [invName, setInvName] = useState('')
  const [invQty, setInvQty] = useState('')
  const [invPrice, setInvPrice] = useState('')
  const [invType, setInvType] = useState('stock')
  const [invLoading, setInvLoading] = useState(false)

  // Goal form
  const [showGoal, setShowGoal] = useState(false)
  const [goalTitle, setGoalTitle] = useState('')
  const [goalTarget, setGoalTarget] = useState('')
  const [goalDate, setGoalDate] = useState('')
  const [goalNote, setGoalNote] = useState('')
  const [goalLoading, setGoalLoading] = useState(false)

  async function loadData() {
    setLoading(true)
    try {
      const [port, gs] = await Promise.all([
        getClientPortfolio(client.id),
        getGoals(client.id),
      ])
      setPortfolio(port)
      setGoals(gs)
    } catch (e) {
      console.error('Failed to load portfolio', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [client.id])

  const holdings = investmentsToHoldings(portfolio?.open_investments ?? [])
  const currentValue = portfolio?.current_value ?? 0
  const cash = portfolio?.available_cash ?? 0
  const unrealizedPnl = portfolio?.unrealized_pnl ?? 0
  const realizedPnl = portfolio?.realized_pnl ?? 0
  const totalPnl = unrealizedPnl + realizedPnl
  const totalInvested = portfolio?.total_invested ?? 0
  const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0

  // Portfolio chart: generate deterministic from currentValue until real history is available
  const seed = client.name.charCodeAt(0) + (client.name.charCodeAt(1) || 0)
  const history = generatePortfolioHistory(currentValue + cash, seed)
  const riskLabel = normaliseRisk(client.risk_profile)

  async function handleDeposit(e: React.FormEvent) {
    e.preventDefault()
    const amt = parseFloat(depositAmount)
    if (!amt || amt <= 0) return
    setDepositLoading(true)
    try {
      await addDeposit(client.id, amt, depositNote)
      setShowDeposit(false); setDepositAmount(''); setDepositNote('')
      await loadData()
      onRefresh?.()
    } catch (err) { console.error(err) }
    finally { setDepositLoading(false) }
  }

  async function handleInvest(e: React.FormEvent) {
    e.preventDefault()
    if (!invSymbol || !invQty || !invPrice) return
    setInvLoading(true)
    try {
      await addInvestment({ client_id: client.id, asset_type: invType, asset_name: invName || invSymbol, symbol: invSymbol.toUpperCase(), quantity: parseFloat(invQty), buy_price: parseFloat(invPrice) })
      setShowInvest(false); setInvSymbol(''); setInvName(''); setInvQty(''); setInvPrice('')
      await loadData()
    } catch (err) { console.error(err) }
    finally { setInvLoading(false) }
  }

  async function handleAddGoal(e: React.FormEvent) {
    e.preventDefault()
    if (!goalTitle || !goalTarget) return
    setGoalLoading(true)
    try {
      await createGoal(client.id, { title: goalTitle, target: parseFloat(goalTarget), target_date: goalDate, note: goalNote })
      setShowGoal(false); setGoalTitle(''); setGoalTarget(''); setGoalDate(''); setGoalNote('')
      const gs = await getGoals(client.id)
      setGoals(gs)
    } catch (err) { console.error(err) }
    finally { setGoalLoading(false) }
  }

  async function handleDeleteGoal(goalId: number) {
    await deleteGoal(client.id, goalId)
    setGoals((prev) => prev.filter((g) => g.id !== goalId))
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-lg font-semibold tracking-tight text-foreground">{client.name}</h2>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${riskTone[riskLabel] ?? riskTone.Balanced}`}>
              {riskLabel}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {client.email} · Joined {client.joined_date ?? '—'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setShowDeposit((v) => !v)} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-sm font-medium text-foreground hover:bg-surface">
            <Plus className="size-4" /> Deposit
          </button>
          <button type="button" onClick={() => setShowInvest((v) => !v)} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-sm font-medium text-foreground hover:bg-surface">
            <Plus className="size-4" /> Investment
          </button>
          <button type="button" onClick={() => setReportOpen(true)} className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <FileText className="size-4" /> Generate report
          </button>
        </div>
      </div>

      {/* Deposit form */}
      {showDeposit && (
        <form onSubmit={handleDeposit} className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Amount (₹)</label>
            <input type="number" value={depositAmount} onChange={(e) => setDepositAmount(e.target.value)} placeholder="100000" className="h-9 w-36 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Note (optional)</label>
            <input value={depositNote} onChange={(e) => setDepositNote(e.target.value)} placeholder="Initial deposit" className="h-9 w-48 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
          </div>
          <button type="submit" disabled={depositLoading} className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-70">
            {depositLoading ? 'Saving…' : 'Record'}
          </button>
          <button type="button" onClick={() => setShowDeposit(false)} className="inline-flex h-9 items-center rounded-md border border-border bg-card px-3 text-sm">
            Cancel
          </button>
        </form>
      )}

      {/* Investment form */}
      {showInvest && (
        <form onSubmit={handleInvest} className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Symbol</label>
            <input value={invSymbol} onChange={(e) => setInvSymbol(e.target.value)} placeholder="RELIANCE.NS" className="h-9 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Name</label>
            <input value={invName} onChange={(e) => setInvName(e.target.value)} placeholder="Reliance Industries" className="h-9 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Type</label>
            <select value={invType} onChange={(e) => setInvType(e.target.value)} className="h-9 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring">
              <option value="stock">Stock</option>
              <option value="etf">ETF</option>
              <option value="crypto">Crypto</option>
              <option value="gold">Gold</option>
              <option value="mutual_fund">Mutual Fund</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Quantity</label>
            <input type="number" value={invQty} onChange={(e) => setInvQty(e.target.value)} placeholder="100" className="h-9 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Buy price (₹)</label>
            <input type="number" value={invPrice} onChange={(e) => setInvPrice(e.target.value)} placeholder="2800" className="h-9 rounded-md border border-input bg-surface px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
          </div>
          <div className="flex items-end gap-2">
            <button type="submit" disabled={invLoading} className="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-70">
              {invLoading ? 'Saving…' : 'Record'}
            </button>
            <button type="button" onClick={() => setShowInvest(false)} className="inline-flex h-9 items-center rounded-md border border-border bg-card px-3 text-sm">×</button>
          </div>
        </form>
      )}

      {loading && (
        <div className="flex items-center justify-center py-16">
          <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
        </div>
      )}

      {!loading && portfolio && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard label="Portfolio value" value={formatCurrency(currentValue + cash, { decimals: 0 })} sub={`incl. ${formatCurrency(cash, { compact: true })} cash`} />
            <StatCard label="Unrealized P/L" value={formatSignedCurrency(unrealizedPnl)} delta={totalPnlPct} deltaFormat={(v) => formatPercent(v)} />
            <StatCard label="Realized P/L" value={formatSignedCurrency(realizedPnl)} />
          </div>

          <section className="rounded-xl border border-border bg-card p-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-medium text-foreground">Portfolio value</h3>
              <Delta value={totalPnl} format={() => `${formatPercent(totalPnlPct)} all time`} showIcon={false} className="text-xs" />
            </div>
            <ValueChart key={client.id} data={history} tone={totalPnl >= 0 ? 'positive' : 'negative'} height={200} formatValue={(v) => formatCurrency(v, { decimals: 0 })} />
          </section>

          {holdings.length > 0 && (
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium text-foreground">Holdings <span className="text-muted-foreground">({holdings.length})</span></h3>
              <HoldingsTable holdings={holdings} />
            </div>
          )}

          {/* Goals */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-foreground">Goals</h3>
              <button type="button" onClick={() => setShowGoal((v) => !v)} className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-card px-2.5 text-xs font-medium text-foreground hover:bg-surface">
                <Plus className="size-3" /> Add goal
              </button>
            </div>

            {showGoal && (
              <form onSubmit={handleAddGoal} className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-surface p-4">
                <div className="col-span-2 flex flex-col gap-1">
                  <label className="text-xs text-muted-foreground">Goal title</label>
                  <input value={goalTitle} onChange={(e) => setGoalTitle(e.target.value)} placeholder="Retirement fund" className="h-9 rounded-md border border-input bg-card px-3 text-sm outline-none focus-visible:border-ring" />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-muted-foreground">Target amount (₹)</label>
                  <input type="number" value={goalTarget} onChange={(e) => setGoalTarget(e.target.value)} placeholder="5000000" className="h-9 rounded-md border border-input bg-card px-3 text-sm outline-none focus-visible:border-ring" />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-muted-foreground">Target year</label>
                  <input value={goalDate} onChange={(e) => setGoalDate(e.target.value)} placeholder="2032" className="h-9 rounded-md border border-input bg-card px-3 text-sm outline-none focus-visible:border-ring" />
                </div>
                <div className="col-span-2 flex flex-col gap-1">
                  <label className="text-xs text-muted-foreground">Note</label>
                  <input value={goalNote} onChange={(e) => setGoalNote(e.target.value)} placeholder="Optional description" className="h-9 rounded-md border border-input bg-card px-3 text-sm outline-none focus-visible:border-ring" />
                </div>
                <div className="col-span-2 flex gap-2">
                  <button type="submit" disabled={goalLoading} className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground disabled:opacity-70">{goalLoading ? 'Saving…' : 'Add goal'}</button>
                  <button type="button" onClick={() => setShowGoal(false)} className="inline-flex h-9 items-center rounded-md border border-border bg-card px-3 text-sm">Cancel</button>
                </div>
              </form>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {goals.map((g) => {
                const pct = Math.min((g.current / g.target) * 100, 100)
                return (
                  <div key={g.id} className="rounded-xl border border-border bg-card p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">{g.title}</span>
                      <div className="flex items-center gap-1">
                        <span className="font-mono text-xs text-muted-foreground">by {g.target_date || '—'}</span>
                        <button type="button" onClick={() => handleDeleteGoal(g.id)} className="ml-1 rounded p-0.5 text-muted-foreground hover:text-foreground">
                          <Trash2 className="size-3" />
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                      <span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="mt-2 flex items-center justify-between font-mono text-xs">
                      <span className="text-foreground">{formatCurrency(g.current, { compact: true })}</span>
                      <span className="text-muted-foreground">{pct.toFixed(0)}% of {formatCurrency(g.target, { compact: true })}</span>
                    </div>
                    {g.note && <p className="mt-2 text-xs text-muted-foreground">{g.note}</p>}
                  </div>
                )
              })}
              {goals.length === 0 && !showGoal && (
                <div className="col-span-2 rounded-xl border border-dashed border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
                  No goals set for this client.
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <ReportDialog open={reportOpen} onClose={() => setReportOpen(false)} subjectLabel={client.name} defaultEmail={client.email} clientId={client.id} />
    </div>
  )
}
