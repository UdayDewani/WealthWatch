'use client'

import { Plus, Target, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formatCurrency } from '@/lib/format'
import { getMyGoals, addMyGoal, deleteMyGoal, type Goal } from '@/lib/api/goals'

export function ClientGoals() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [target, setTarget] = useState('')
  const [date, setDate] = useState('')
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getMyGoals()
      .then(setGoals)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  async function addGoal(e: React.FormEvent) {
    e.preventDefault()
    const targetNum = Number(target)
    if (!title.trim() || !targetNum) return
    setSubmitting(true)
    setError('')
    try {
      const res = await addMyGoal({
        title: title.trim(),
        target: targetNum,
        target_date: date,
        note: note.trim(),
      })
      const newGoal: Goal = {
        id: res.id,
        client_id: 0,
        title: title.trim(),
        target: targetNum,
        current: 0,
        target_date: date || '—',
        note: note.trim(),
        created_at: new Date().toISOString(),
      }
      setGoals((prev) => [newGoal, ...prev])
      setTitle('')
      setTarget('')
      setDate('')
      setNote('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add goal')
    } finally {
      setSubmitting(false)
    }
  }

  async function removeGoal(id: number) {
    await deleteMyGoal(id)
    setGoals((prev) => prev.filter((g) => g.id !== id))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-pretty text-2xl font-semibold tracking-tight text-foreground">
          Your goals
        </h1>
        <p className="text-pretty text-sm leading-relaxed text-muted-foreground">
          The things your wealth is working toward. Set a goal, and your advisor
          will help shape a plan to reach it.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Progress view */}
        <div className="flex flex-col gap-4">
          {goals.map((g) => {
            const pct = Math.min(g.target > 0 ? (g.current / g.target) * 100 : 0, 100)
            const remaining = Math.max(g.target - g.current, 0)
            return (
              <article
                key={g.id}
                className="rounded-xl border border-border bg-card p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="grid size-9 place-items-center rounded-lg bg-accent text-accent-foreground">
                      <Target className="size-4" />
                    </span>
                    <div>
                      <h2 className="text-base font-medium text-foreground">
                        {g.title}
                      </h2>
                      <p className="text-xs text-muted-foreground">
                        Target {g.target_date || '—'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold tabular text-foreground">
                      {pct.toFixed(0)}%
                    </span>
                    <button
                      type="button"
                      onClick={() => removeGoal(g.id)}
                      className="rounded p-1 text-muted-foreground hover:text-foreground"
                      aria-label="Delete goal"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                </div>

                {g.note && (
                  <p className="mt-3 text-pretty text-sm leading-relaxed text-muted-foreground">
                    {g.note}
                  </p>
                )}

                <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full bg-primary transition-[width] duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="mt-2.5 flex items-center justify-between font-mono text-xs">
                  <span className="text-foreground">
                    {formatCurrency(g.current, { compact: true })} saved
                  </span>
                  <span className="text-muted-foreground">
                    {formatCurrency(remaining, { compact: true })} to go ·{' '}
                    {formatCurrency(g.target, { compact: true })} goal
                  </span>
                </div>
              </article>
            )
          })}
          {goals.length === 0 && (
            <div className="rounded-xl border border-dashed border-border bg-card p-10 text-center text-sm text-muted-foreground">
              You haven&apos;t set any goals yet. Add your first one to get
              started.
            </div>
          )}
        </div>

        {/* Add goal form */}
        <form
          onSubmit={addGoal}
          className="flex h-fit flex-col gap-4 rounded-xl border border-border bg-surface p-5 lg:sticky lg:top-20"
        >
          <h2 className="text-sm font-medium text-foreground">Add a goal</h2>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="g-title" className="text-sm text-foreground">
              What are you saving for?
            </label>
            <input
              id="g-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. A home in Goa"
              className="h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="g-target" className="text-sm text-foreground">
              Target amount
            </label>
            <div className="flex h-10 items-center gap-1 rounded-md border border-input bg-card px-3 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/40">
              <span className="text-sm text-muted-foreground">₹</span>
              <input
                id="g-target"
                type="number"
                min="0"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="1,000,000"
                className="h-full flex-1 bg-transparent font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="g-date" className="text-sm text-foreground">
              Target year
            </label>
            <input
              id="g-date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              placeholder="2032"
              className="h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="g-note" className="text-sm text-foreground">
              A note (optional)
            </label>
            <textarea
              id="g-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Why this matters to you…"
              className="resize-none rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-70"
          >
            <Plus className="size-4" />
            {submitting ? 'Adding…' : 'Add goal'}
          </button>
        </form>
      </div>
    </div>
  )
}
