import { authJson } from './client'

export type ApiClient = {
  id: number
  name: string
  email: string
  phone: string
  pan: string
  risk_profile: string
  joined_date: string
  notes: string
  total_deposited?: number
  total_invested?: number
}

export type CreateClientPayload = {
  name: string
  email: string
  password: string
  phone?: string
  pan?: string
  risk_profile?: string
  joined_date?: string
  notes?: string
}

export async function getClients(): Promise<ApiClient[]> {
  return authJson<ApiClient[]>('/api/clients')
}

export async function createClient(data: CreateClientPayload): Promise<{ id: number }> {
  return authJson('/api/clients', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateClient(id: number, data: Partial<CreateClientPayload>): Promise<void> {
  await authJson(`/api/clients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteClient(id: number): Promise<void> {
  await authJson(`/api/clients/${id}`, { method: 'DELETE' })
}
