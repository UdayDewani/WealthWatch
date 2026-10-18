import { AppShell } from '@/components/app-shell'

const nav = [
  { label: 'Dashboard', href: '/manager/dashboard' },
  { label: 'Market Overview', href: '/manager' },
  { label: 'Stock Intelligence', href: '/manager/stock-analysis' },
  { label: 'Clients', href: '/manager/clients' },
]

export default function ManagerLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AppShell role="manager" nav={nav} reportSubject="All clients — book summary">
      {children}
    </AppShell>
  )
}
