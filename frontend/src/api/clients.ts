export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  pan: string;
  risk_profile: 'conservative' | 'moderate' | 'aggressive';
  aum: number;
  joined_date: string;
  notes: string;
}

export type ClientCreate = Omit<Client, 'id'>;
export type ClientUpdate = Partial<ClientCreate>;

const BASE = '/api/clients';

export async function fetchClients(): Promise<Client[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error('Failed to fetch clients');
  const data = await res.json();
  return data.clients as Client[];
}

export async function createClient(payload: ClientCreate): Promise<Client> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create client');
  return res.json();
}

export async function updateClient(id: number, payload: ClientUpdate): Promise<Client> {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update client');
  return res.json();
}

export async function deleteClient(id: number): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw new Error('Failed to delete client');
}
