'use client'

import { FileText, LogOut } from 'lucide-react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { ReportDialog } from '@/components/report-dialog'
import { ThemeToggle } from '@/components/theme-toggle'
import { Wordmark } from '@/components/wordmark'
import { cn } from '@/lib/utils'
import { clearSession, type Session } from '@/lib/session'

export type NavItem = { label: string; href: string }

function initials(name: string) {
  return name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export function TopNav({
  nav,
  session,
  reportSubject,
}: {
  nav: NavItem[]
  session: Session | null
  reportSubject: string
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const name = session?.name ?? 'Guest'
  const email = session?.email ?? ''

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  function isActive(href: string) {
    if (href === pathname) return true
    // treat sub-routes as active for the section root, but keep exact roots exact
    return false
  }

  function signOut() {
    clearSession()
    router.push('/')
  }

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-6">
            <Link
              href={nav[0]?.href ?? '/'}
              className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Wordmark />
            </Link>
            <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive(item.href) ? 'page' : undefined}
                  className={cn(
                    'relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive(item.href)
                      ? 'text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {item.label}
                  {isActive(item.href) && (
                    <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-primary" />
                  )}
                </Link>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setReportOpen(true)}
              className="hidden h-8 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:inline-flex"
            >
              <FileText className="size-3.5 text-muted-foreground" />
              Report
            </button>
            <ThemeToggle />

            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex items-center gap-2 rounded-md py-1 pl-1 pr-1.5 transition-colors hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="grid size-7 place-items-center rounded-full bg-primary/12 text-xs font-semibold text-primary ring-1 ring-primary/20">
                  {initials(name)}
                </span>
                <span className="hidden text-sm font-medium text-foreground lg:block">
                  {name}
                </span>
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 top-full mt-2 w-56 overflow-hidden rounded-lg border border-border bg-popover shadow-lg animate-in fade-in slide-in-from-top-1"
                >
                  <div className="border-b border-border px-3 py-2.5">
                    <p className="text-sm font-medium text-foreground">{name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {email}
                    </p>
                  </div>
                  <div className="p-1 sm:hidden">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuOpen(false)
                        setReportOpen(true)
                      }}
                      className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-foreground transition-colors hover:bg-surface"
                    >
                      <FileText className="size-4 text-muted-foreground" />
                      Generate report
                    </button>
                  </div>
                  <div className="p-1">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={signOut}
                      className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-foreground transition-colors hover:bg-surface"
                    >
                      <LogOut className="size-4 text-muted-foreground" />
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Mobile nav tabs */}
        <nav
          className="flex items-center gap-1 overflow-x-auto border-t border-border px-4 py-1.5 md:hidden"
          aria-label="Primary mobile"
        >
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? 'page' : undefined}
              className={cn(
                'shrink-0 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                isActive(item.href)
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground',
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>

      <ReportDialog
        open={reportOpen}
        onClose={() => setReportOpen(false)}
        subjectLabel={reportSubject}
        defaultEmail={email || 'you@example.com'}
      />
    </>
  )
}
