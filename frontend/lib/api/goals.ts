import { authJson } from './client'

export type Goal = {
  id: number
  client_id: number
  title: string
  target: number
  current: number
  target_date: string
  note: string
  created_at: string
}

export type CreateGoalPayload = {
  title: string
  target: number
  current?: number
  target_date?: string
  note?: string
}

// ── WM endpoints (for managing client goals) ──────────────────────────────────

export async function getGoals(clientId: number): Promise<Goal[]> {
  return authJson<Goal[]>(`/api/clients/${clientId}/goals`)
}

export async function createGoal(
  clientId: number,
  data: CreateGoalPayload,
): Promise<{ id: number }> {
  return authJson<{ id: number }>(`/api/clients/${clientId}/goals`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteGoal(
  clientId: number,
  goalId: number,
): Promise<void> {
  await authJson(`/api/clients/${clientId}/goals/${goalId}`, {
    method: 'DELETE',
  })
}

// ── Client portal endpoints (client managing own goals) ───────────────────────

export async function getMyGoals(): Promise<Goal[]> {
  return authJson<Goal[]>('/api/client/me/goals')
}

export async function addMyGoal(
  data: CreateGoalPayload,
): Promise<{ id: number }> {
  return authJson<{ id: number }>('/api/client/me/goals', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteMyGoal(goalId: number): Promise<void> {
  await authJson(`/api/client/me/goals/${goalId}`, { method: 'DELETE' })
}
