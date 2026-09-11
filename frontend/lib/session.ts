'use client'

import { useEffect, useState } from 'react'

export type Role = 'manager' | 'client'

const KEY = 'ww-session'
const TOKEN_KEY = 'ww-token'

export type Session = {
  role: Role
  name: string
  email: string
}

export function saveSession(s: Session, token: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(KEY, JSON.stringify(s))
  window.localStorage.setItem(TOKEN_KEY, token)
}

export function readSession(): Session | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(TOKEN_KEY)
}

export function clearSession() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(KEY)
  window.localStorage.removeItem(TOKEN_KEY)
}

export function useSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    setSession(readSession())
    setReady(true)
  }, [])
  return { session, ready }
}
