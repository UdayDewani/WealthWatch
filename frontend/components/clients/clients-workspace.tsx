'use client'

import { Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { ClientDetail } from '@/components/clients/client-detail'
import { Delta } from '@/components/delta'
import { getClients, createClient, type ApiClient } from '@/lib/api/clients'
import { formatCurrency, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'

function normaliseRisk(raw: string): string {
  const map: Record<string, string> = {
    conservative: 'Conservative',
    balanced: 'Balanced',
    growth: 'Growth',
    aggressive: 'Aggressive',
    moderate: 'Moderate',
  }
  return map[raw?.toLowerCase()] ?? raw ?? 'Balanced'
}

export function ClientsWorkspace() {
  const [clients, setClients] = useState<ApiClient[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)

  // Add-client form state
  const [newName, setNewName] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRisk, setNewRisk] = useState('balanced')
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState('')

  async function loadClients() {
    setLoading(true)
    try {
      const data = await getClients()
      setClients(data)
      if (data.length > 0 && !selectedId) setSelectedId(data[0].id)
    } catch (e) {
      console.error('Failed to load clients', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadClients() }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return clients.filter((c) => !q || c.name.toLowerCase().includes(q))
  }, [query, clients])

  const selected = clients.find((c) => c.id === selectedId) ?? clients[0] ?? null

  const totalAum = clients.reduce((s, c) => s + (c.total_deposited ?? 0), 0)

  async function handleAddClient(e: React.FormEvent) {
    e.preventDefault()
    if (!newName || !newEmail || !newPassword) { setAddError('All fields are required.'); return }
    setAddLoading(true)
    setAddError('')
    try {
      await createClient({ name: newName, email: newEmail, password: newPassword, risk_profile: newRisk })
      setShowAdd(false)
      setNewName(''); setNewEmail(''); setNewPassword('')
      await loadClients()
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to create client')
    } finally {
      setAddLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Clients</h1>
          <p className="text-sm text-muted-foreground">
            {loading ? 'Loading…' : `${clients.length} relationships · ${formatCurrency(totalAum, { compact: true })} under management`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAdd((v) => !v)}
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus className="size-4" />
          Add client
        </button>
      </div>

      {/* Add client form */}
      {showAdd && (
        <form onSubmit={handleAddClient} className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-4 text-sm font-medium text-foreground">New client</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-foreground">Full name</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Eleanor Harrington" className="h-10 rounded-md border border-input bg-surface px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-foreground">Email</label>
              <input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="client@example.com" className="h-10 rounded-md border border-input bg-surface px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-foreground">Password (for client portal)</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="••••••••" className="h-10 rounded-md border border-input bg-surface px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-foreground">Risk profile</label>
              <select value={newRisk} onChange={(e) => setNewRisk(e.target.value)} className="h-10 rounded-md border border-input bg-surface px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40">
                <option value="conservative">Conservative</option>
                <option value="balanced">Balanced</option>
                <option value="moderate">Moderate</option>
                <option value="growth">Growth</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          </div>
          {addError && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{addError}</p>}
          <div className="mt-4 flex items-center gap-2">
            <button type="submit" disabled={addLoading} className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3.5 text-sm font-medium text-primary-foreground disabled:opacity-70">
              {addLoading ? 'Creating…' : 'Create client'}
            </button>
            <button type="button" onClick={() => setShowAdd(false)} className="inline-flex h-9 items-center rounded-md border border-border bg-card px-3.5 text-sm font-medium text-foreground">
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading && (
        <div className="flex items-center justify-center py-20">
          <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
        </div>
      )}

      {!loading && clients.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-card p-10 text-center text-sm text-muted-foreground">
          No clients yet. Click &ldquo;Add client&rdquo; to get started.
        </div>
      )}

      {!loading && clients.length > 0 && (
        <>
          {/* Mobile switcher strip */}
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 lg:hidden">
            {clients.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedId(c.id)}
                className={cn(
                  'shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors',
                  c.id === selectedId ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground',
                )}
              >
                {c.name.split(' ')[0]}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[300px_1fr]">
            {/* Persistent sidebar */}
            <aside className="hidden lg:sticky lg:top-20 lg:block lg:self-start">
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <div className="border-b border-border p-2.5">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Find client"
                      aria-label="Find client"
                      className="h-8 w-full rounded-md border border-input bg-surface pl-8 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                    />
                  </div>
                </div>
                <ul className="max-h-[calc(100dvh-11rem)] overflow-y-auto">
                  {filtered.map((c) => {
                    const active = c.id === selectedId
                    const deposited = c.total_deposited ?? 0
                    return (
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => setSelectedId(c.id)}
                          aria-current={active ? 'true' : undefined}
                          className={cn(
                            'relative flex w-full flex-col gap-1 border-b border-border/60 px-3.5 py-3 text-left transition-colors last:border-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                            active ? 'bg-accent/60' : 'hover:bg-surface',
                          )}
                        >
                          {active && <span className="absolute inset-y-0 left-0 w-0.5 bg-primary" />}
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-sm font-medium text-foreground">{c.name}</span>
                            <span className="shrink-0 text-xs text-muted-foreground">{normaliseRisk(c.risk_profile)}</span>
                          </div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-sm tabular text-foreground">{formatCurrency(deposited, { compact: true })}</span>
                            <span className="text-xs text-muted-foreground">deposited</span>
                          </div>
                        </button>
                      </li>
                    )
                  })}
                  {filtered.length === 0 && (
                    <li className="px-3.5 py-6 text-center text-sm text-muted-foreground">No matches</li>
                  )}
                </ul>
              </div>
            </aside>

            {selected ? (
              <ClientDetail client={selected} onRefresh={loadClients} />
            ) : (
              <div className="py-20 text-center text-sm text-muted-foreground">Select a client</div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
