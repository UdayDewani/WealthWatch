'use client'

import { ArrowUpRight, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { ThemeToggle } from '@/components/theme-toggle'
import { Wordmark } from '@/components/wordmark'
import { loginWM, loginClient, registerWM } from '@/lib/api/auth'
import { type Role, saveSession } from '@/lib/session'

type Mode = 'signin' | 'register'

const roleCopy: Record<Role, { title: string; sub: string; placeholder: string }> = {
  manager: {
    title: 'Advisor workspace',
    sub: 'Markets, client books, and reporting in one calm view.',
    placeholder: 'advisor@example.com',
  },
  client: {
    title: 'Your portfolio',
    sub: 'A clear picture of where you stand and where you are headed.',
    placeholder: 'you@example.com',
  },
}

export function LoginScreen() {
  const router = useRouter()
  const [role, setRole] = useState<Role>('manager')
  const [mode, setMode] = useState<Mode>('signin')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email || !password) {
      setError('Please enter your email and password.')
      return
    }
    setError('')
    setLoading(true)
    try {
      let resp
      if (mode === 'register' && role === 'manager') {
        if (!name.trim()) {
          setError('Please enter your name.')
          setLoading(false)
          return
        }
        resp = await registerWM(name.trim(), email, password)
      } else if (role === 'manager') {
        resp = await loginWM(email, password)
      } else {
        resp = await loginClient(email, password)
      }
      saveSession(
        { role, name: resp.name, email: resp.email },
        resp.token,
      )
      router.push(role === 'manager' ? '/manager' : '/client')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="grid min-h-dvh grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
      {/* Brand panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-surface p-10 lg:flex">
        <div className="flex items-center justify-between">
          <Wordmark />
          <span className="font-mono text-xs text-muted-foreground">
            EST. 1998 · PRIVATE WEALTH
          </span>
        </div>

        <div className="max-w-md">
          <h1 className="text-pretty text-3xl font-semibold leading-tight tracking-tight text-foreground">
            Manage wealth with the precision it deserves.
          </h1>
          <p className="mt-4 text-pretty leading-relaxed text-muted-foreground">
            Live markets, portfolio intelligence, and client reporting — held to
            a private-banking standard of clarity and care.
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card p-6">
          <p className="text-sm font-medium text-foreground">WealthWatch 2.0</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Powered by real-time market data, LangGraph AI analysis, and live
            portfolio tracking across all asset classes.
          </p>
          <ul className="mt-4 space-y-1.5 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-positive" />
              Live Nifty &amp; Sensex via Upstox
            </li>
            <li className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-positive" />
              AI market analysis via Gemini + LangGraph
            </li>
            <li className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-positive" />
              Real-time portfolio P&amp;L
            </li>
          </ul>
        </div>
      </section>

      {/* Form panel */}
      <section className="relative flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="absolute right-6 top-6 flex items-center gap-3">
          <ThemeToggle />
        </div>

        <div className="mx-auto w-full max-w-sm">
          <div className="lg:hidden">
            <Wordmark />
          </div>

          <div className="mt-8 lg:mt-0">
            <h2 className="text-xl font-semibold tracking-tight text-foreground">
              {mode === 'register' ? 'Create account' : 'Sign in'}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {roleCopy[role].sub}
            </p>
          </div>

          {/* Role selector */}
          <div
            role="radiogroup"
            aria-label="Account type"
            className="mt-6 grid grid-cols-2 gap-1 rounded-lg border border-border bg-surface p-1"
          >
            {(['manager', 'client'] as Role[]).map((r) => (
              <button
                key={r}
                type="button"
                role="radio"
                aria-checked={role === r}
                onClick={() => { setRole(r); setMode('signin'); setError('') }}
                className={`rounded-md px-3 py-2 text-sm font-medium capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface ${
                  role === r
                    ? 'bg-card text-foreground shadow-sm ring-1 ring-border'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            {mode === 'register' && role === 'manager' && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="name" className="text-sm font-medium text-foreground">
                  Full name
                </label>
                <input
                  id="name"
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Morgan Ashford"
                  className="h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none transition-shadow placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                />
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-sm font-medium text-foreground">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={roleCopy[role].placeholder}
                className="h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none transition-shadow placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-sm font-medium text-foreground">
                  Password
                </label>
              </div>
              <input
                id="password"
                type="password"
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••"
                className="h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none transition-shadow placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>

            {error && (
              <p className="rounded-md bg-negative-muted px-3 py-2 text-sm text-negative">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-1 inline-flex h-10 items-center justify-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-70"
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <ArrowUpRight className="size-4" />
              )}
              {mode === 'register' ? 'Create account' : `Enter ${roleCopy[role].title}`}
            </button>
          </form>

          {role === 'manager' && (
            <p className="mt-4 text-center text-xs text-muted-foreground">
              {mode === 'signin' ? (
                <>
                  New advisor?{' '}
                  <button
                    type="button"
                    onClick={() => { setMode('register'); setError('') }}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Create an account
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => { setMode('signin'); setError('') }}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Sign in
                  </button>
                </>
              )}
            </p>
          )}

        </div>
      </section>
    </main>
  )
}
