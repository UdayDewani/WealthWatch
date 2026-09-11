import { AppShell } from '@/components/app-shell'

const nav = [
  { label: 'Portfolio', href: '/client' },
  { label: 'Goals', href: '/client/goals' },
]

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AppShell role="client" nav={nav} reportSubject="Your portfolio">
      {children}
    </AppShell>
  )
}
