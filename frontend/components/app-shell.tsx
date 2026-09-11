'use client'

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { type NavItem, TopNav } from '@/components/top-nav'
import { type Role, useSession } from '@/lib/session'

export function AppShell({
  role,
  nav,
  reportSubject,
  children,
}: {
  role: Role
  nav: NavItem[]
  reportSubject: string
  children: React.ReactNode
}) {
  const { session, ready } = useSession()
  const router = useRouter()

  useEffect(() => {
    if (ready && (!session || session.role !== role)) {
      router.replace('/')
    }
  }, [ready, session, role, router])

  if (!ready || !session || session.role !== role) {
    return (
      <div className="grid min-h-dvh place-items-center bg-background">
        <span className="size-5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
      </div>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <TopNav nav={nav} session={session} reportSubject={reportSubject} />
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">
        {children}
      </main>
    </div>
  )
}
