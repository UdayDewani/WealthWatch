export type AuthResponse = {
  token: string
  role: 'wm' | 'client'
  name: string
  email: string
}

export async function loginWM(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch('/api/auth/wm-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Invalid credentials')
  }
  return res.json()
}

export async function loginClient(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch('/api/auth/client-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Invalid credentials')
  }
  return res.json()
}

export async function registerWM(name: string, email: string, password: string): Promise<AuthResponse> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Registration failed')
  }
  return res.json()
}
