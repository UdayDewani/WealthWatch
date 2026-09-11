import { authJson } from './client'

export type Investment = {
  id: number
  client_id: number
  asset_type: string
  asset_name: string
  symbol: string
  quantity: number
  buy_price: number
  buy_date: string
  sell_price: number | null
  sell_date: string | null
  status: 'open' | 'closed'
  notes: string
  current_price?: number | null
  current_value?: number
  pnl?: number
  pnl_pct?: number
}

export type Deposit = {
  id: number
  client_id: number
  amount: number
  note: string
  deposited_at: string
}

export type Portfolio = {
  total_deposited: number
  total_invested: number
  available_cash: number
  current_value: number
  unrealized_pnl: number
  realized_pnl: number
  open_investments: Investment[]
  closed_investments?: Investment[]
  deposits?: Deposit[]
}

export type AddInvestmentPayload = {
  client_id: number
  asset_type: string
  asset_name: string
  symbol: string
  quantity: number
  buy_price: number
  notes?: string
}

/** Get portfolio for a specific client (WM view) */
export async function getClientPortfolio(clientId: number): Promise<Portfolio> {
  return authJson<Portfolio>(`/api/clients/${clientId}/portfolio`)
}

/** Get the logged-in client's own portfolio */
export async function getMyPortfolio(): Promise<Portfolio> {
  return authJson<Portfolio>('/api/client/me/portfolio')
}

/** Record a deposit for a client */
export async function addDeposit(
  clientId: number,
  amount: number,
  note?: string,
): Promise<{ id: number }> {
  return authJson('/api/deposits', {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId, amount, note: note ?? '' }),
  })
}

/** Add a new investment for a client */
export async function addInvestment(
  payload: AddInvestmentPayload,
): Promise<{ id: number }> {
  return authJson('/api/investments', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** Close an investment by recording sell price */
export async function closeInvestment(
  invId: number,
  clientId: number,
  sellPrice: number,
): Promise<void> {
  await authJson(`/api/investments/${invId}/close?client_id=${clientId}`, {
    method: 'POST',
    body: JSON.stringify({ sell_price: sellPrice }),
  })
}
