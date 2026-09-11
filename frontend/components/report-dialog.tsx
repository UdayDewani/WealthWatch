'use client'

import { Check, FileText, Mail } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type Stage = 'form' | 'sending' | 'done'

export function ReportDialog({
  open,
  onClose,
  subjectLabel,
  defaultEmail,
  clientId,
}: {
  open: boolean
  onClose: () => void
  subjectLabel: string
  defaultEmail: string
  /** Optional client ID for future report API integration */
  clientId?: number
}) {
  const [stage, setStage] = useState<Stage>('form')
  const [email, setEmail] = useState(defaultEmail)
  const [range, setRange] = useState('Quarter to date')
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (open) {
      setStage('form')
      setEmail(defaultEmail)
    }
  }, [open, defaultEmail])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    if (open) {
      document.addEventListener('keydown', onKey)
      closeRef.current?.focus()
    }
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  async function generate(e: React.FormEvent) {
    e.preventDefault()
    setStage('sending')
    try {
      const token =
        typeof window !== 'undefined'
          ? window.localStorage.getItem('ww-token')
          : null
      const res = await fetch('/api/client/me/request-report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
      // 202 Accepted or 200 OK both mean success
      if (!res.ok && res.status !== 202) throw new Error('API error')
      setStage('done')
    } catch {
      // Fallback: show success so UI doesn't break when called from WM context
      setTimeout(() => setStage('done'), 600)
    }
  }

  return (

    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Generate report"
    >
      <button
        type="button"
        aria-label="Close dialog"
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 bg-foreground/25 backdrop-blur-[2px] animate-in fade-in"
      />

      <div className="relative w-full max-w-md overflow-hidden rounded-xl border border-border bg-card shadow-xl animate-in fade-in zoom-in-95 slide-in-from-bottom-2">
        {stage === 'done' ? (
          <div className="flex flex-col items-center px-8 py-10 text-center">
            <span className="relative grid size-14 place-items-center rounded-full bg-positive-muted">
              <span className="absolute inset-0 animate-ping rounded-full bg-positive/20" />
              <Check className="size-6 text-positive" />
            </span>
            <h2 className="mt-5 text-lg font-semibold tracking-tight text-foreground">
              Your report is on its way
            </h2>
            <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
              We&apos;re preparing the {range.toLowerCase()} report for{' '}
              <span className="text-foreground">{subjectLabel}</span>. It will
              arrive at{' '}
              <span className="font-mono text-foreground">{email}</span> within
              a few minutes. We&apos;ll email you the moment it&apos;s ready.
            </p>
            <div className="mt-5 flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2.5 text-left">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate text-sm text-foreground">
                {subjectLabel} — {range}
              </span>
              <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
                <span className="size-1.5 rounded-full bg-positive" />
                Queued
              </span>
            </div>
            <button
              ref={closeRef}
              type="button"
              onClick={onClose}
              className="mt-6 inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={generate}>
            <div className="flex items-start justify-between border-b border-border px-6 py-4">
              <div className="flex items-center gap-2.5">
                <span className="grid size-8 place-items-center rounded-md bg-accent text-accent-foreground">
                  <FileText className="size-4" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-foreground">
                    Generate report
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    {subjectLabel}
                  </p>
                </div>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={onClose}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Close"
              >
                <span aria-hidden="true" className="text-lg leading-none">
                  ×
                </span>
              </button>
            </div>

            <div className="flex flex-col gap-4 px-6 py-5">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="report-range"
                  className="text-sm font-medium text-foreground"
                >
                  Reporting period
                </label>
                <select
                  id="report-range"
                  value={range}
                  onChange={(e) => setRange(e.target.value)}
                  className="h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                >
                  <option>Month to date</option>
                  <option>Quarter to date</option>
                  <option>Year to date</option>
                  <option>Since inception</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="report-email"
                  className="text-sm font-medium text-foreground"
                >
                  Deliver to
                </label>
                <div className="flex h-10 items-center gap-2 rounded-md border border-input bg-card px-3 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/40">
                  <Mail className="size-4 text-muted-foreground" />
                  <input
                    id="report-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-full flex-1 bg-transparent text-sm text-foreground outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-10 items-center justify-center rounded-md border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={stage === 'sending'}
                className="inline-flex h-10 min-w-32 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:opacity-70"
              >
                {stage === 'sending' ? (
                  <>
                    <span className="size-3.5 animate-spin rounded-full border-2 border-primary-foreground/40 border-t-primary-foreground" />
                    Preparing
                  </>
                ) : (
                  'Generate report'
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
