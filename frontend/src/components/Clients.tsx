import { useState, useEffect, useCallback } from 'react';
import type { Client, ClientCreate, ClientUpdate } from '../api/clients';
import { fetchClients, createClient, updateClient, deleteClient } from '../api/clients';
import ClientModal from './ClientModal';
import Portfolio from './Portfolio';

const RISK_COLORS: Record<string, string> = {
  conservative: '#059669',
  moderate:     '#d97706',
  aggressive:   '#dc2626',
};

const RISK_BG: Record<string, string> = {
  conservative: '#dcfce7',
  moderate:     '#fef9c3',
  aggressive:   '#fef2f2',
};

function fmt(n: number) {
  if (n >= 1_00_00_000) return '₹' + (n / 1_00_00_000).toFixed(2) + 'Cr';
  if (n >= 1_00_000)    return '₹' + (n / 1_00_000).toFixed(2) + 'L';
  return '₹' + n.toLocaleString('en-IN');
}

function initials(name: string) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

export default function Clients() {
  const [clients, setClients]       = useState<Client[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [search, setSearch]         = useState('');
  const [riskFilter, setRiskFilter] = useState('all');
  const [modalOpen, setModalOpen]   = useState(false);
  const [editing, setEditing]       = useState<Client | null>(null);
  const [confirmId, setConfirmId]   = useState<number | null>(null);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchClients();
      setClients(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load clients');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── derived stats ────────────────────────────────────────────────────
  const totalAum = clients.reduce((s, c) => s + c.aum, 0);
  const riskCounts = {
    conservative: clients.filter(c => c.risk_profile === 'conservative').length,
    moderate:     clients.filter(c => c.risk_profile === 'moderate').length,
    aggressive:   clients.filter(c => c.risk_profile === 'aggressive').length,
  };

  // ── filtered list ────────────────────────────────────────────────────
  const filtered = clients.filter(c => {
    const q = search.toLowerCase();
    const matchSearch = !q || c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q) || c.pan.toLowerCase().includes(q);
    const matchRisk   = riskFilter === 'all' || c.risk_profile === riskFilter;
    return matchSearch && matchRisk;
  });

  // ── handlers ─────────────────────────────────────────────────────────
  const handleSave = async (data: ClientCreate | ClientUpdate) => {
    if (editing) {
      const updated = await updateClient(editing.id, data as ClientUpdate);
      setClients(prev => prev.map(c => c.id === editing.id ? updated : c));
    } else {
      const created = await createClient(data as ClientCreate);
      setClients(prev => [...prev, created]);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteClient(id);
    setClients(prev => prev.filter(c => c.id !== id));
    setConfirmId(null);
  };

  const openAdd  = () => { setEditing(null); setModalOpen(true); };
  const openEdit = (c: Client) => { setEditing(c); setModalOpen(true); };

  // ── render ───────────────────────────────────────────────────────────
  // If a client is selected → show their portfolio
  if (selectedClient) {
    return <Portfolio client={selectedClient} onBack={() => setSelectedClient(null)} />;
  }

  return (
    <>
      {/* Page header */}
      <div className="dash-header">
        <h1>Clients</h1>
        <button className="btn-primary" onClick={openAdd} id="add-client-btn">
          + Add Client
        </button>
      </div>

      {/* Stats bar */}
      <div className="client-stats">
        <div className="stat-card">
          <div className="label">Total Clients</div>
          <div className="value">{clients.length}</div>
          <div className="sub" style={{ color: 'var(--text-secondary)' }}>Active accounts</div>
        </div>
        <div className="stat-card">
          <div className="label">Total AUM</div>
          <div className="value">{fmt(totalAum)}</div>
          <div className="sub" style={{ color: 'var(--text-secondary)' }}>Assets under management</div>
        </div>
        <div className="stat-card">
          <div className="label">Risk Breakdown</div>
          <div className="risk-chips" style={{ marginTop: 8 }}>
            <span className="risk-chip" style={{ background: RISK_BG.conservative, color: RISK_COLORS.conservative }}>
              {riskCounts.conservative} Conservative
            </span>
            <span className="risk-chip" style={{ background: RISK_BG.moderate, color: RISK_COLORS.moderate }}>
              {riskCounts.moderate} Moderate
            </span>
            <span className="risk-chip" style={{ background: RISK_BG.aggressive, color: RISK_COLORS.aggressive }}>
              {riskCounts.aggressive} Aggressive
            </span>
          </div>
        </div>
      </div>

      {/* Search & filter */}
      <div className="card">
        <div className="table-toolbar">
          <div className="search-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              placeholder="Search by name, email or PAN..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              id="client-search"
            />
          </div>
          <select
            className="sort-btn"
            value={riskFilter}
            onChange={e => setRiskFilter(e.target.value)}
            id="risk-filter"
          >
            <option value="all">All Risk Profiles</option>
            <option value="conservative">Conservative</option>
            <option value="moderate">Moderate</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>

        {loading && (
          <div className="empty-state">
            <p>Loading clients...</p>
          </div>
        )}

        {!loading && error && (
          <div className="empty-state">
            <h3>Could not load clients</h3>
            <p style={{ marginTop: 8 }}>{error}</p>
            <button className="btn-primary" style={{ marginTop: 16 }} onClick={load}>Retry</button>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="empty-state">
            <h3>{clients.length === 0 ? 'No clients yet' : 'No results found'}</h3>
            <p style={{ marginTop: 8, marginBottom: 16 }}>
              {clients.length === 0
                ? 'Click "Add Client" to onboard your first customer.'
                : 'Try adjusting your search or filter.'}
            </p>
            {clients.length === 0 && (
              <button className="btn-primary" onClick={openAdd}>+ Add Client</button>
            )}
          </div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Contact</th>
                  <th>PAN</th>
                  <th>Risk Profile</th>
                  <th style={{ textAlign: 'right' }}>AUM</th>
                  <th>Since</th>
                  <th style={{ textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <tr
                    key={c.id}
                    className="client-row"
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedClient(c)}
                  >
                    <td>
                      <div className="stock-info">
                        <div className="client-avatar" style={{
                          background: `hsl(${(c.id * 47) % 360}, 60%, 88%)`,
                          color: `hsl(${(c.id * 47) % 360}, 50%, 30%)`
                        }}>
                          {initials(c.name)}
                        </div>
                        <div>
                          <div className="stock-name">{c.name}</div>
                          <div className="stock-symbol">{c.notes ? c.notes.slice(0, 40) + (c.notes.length > 40 ? '…' : '') : '—'}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className="stock-name">{c.email}</div>
                      <div className="stock-symbol">{c.phone}</div>
                    </td>
                    <td>
                      <span className="pan-badge">{c.pan || '—'}</span>
                    </td>
                    <td>
                      <span
                        className="risk-chip"
                        style={{
                          background: RISK_BG[c.risk_profile],
                          color: RISK_COLORS[c.risk_profile],
                        }}
                      >
                        {c.risk_profile.charAt(0).toUpperCase() + c.risk_profile.slice(1)}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>
                      {fmt(c.aum)}
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                      {new Date(c.joined_date).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="action-btns">
                        <button
                          className="action-btn edit"
                          onClick={(e) => { e.stopPropagation(); openEdit(c); }}
                          title="Edit client"
                          id={`edit-client-${c.id}`}
                        >
                          ✏️
                        </button>
                        <button
                          className="action-btn delete"
                          onClick={(e) => { e.stopPropagation(); setConfirmId(c.id); }}
                          title="Delete client"
                          id={`delete-client-${c.id}`}
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add / Edit modal */}
      <ClientModal
        open={modalOpen}
        client={editing}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
      />

      {/* Delete confirmation */}
      {confirmId !== null && (
        <div className="modal-overlay" onClick={() => setConfirmId(null)}>
          <div className="modal confirm-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Delete Client</h3>
              <button className="drawer-close" onClick={() => setConfirmId(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
                Are you sure you want to delete this client? This action cannot be undone.
              </p>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setConfirmId(null)}>Cancel</button>
                <button
                  className="btn-danger"
                  onClick={() => handleDelete(confirmId)}
                  id="confirm-delete-btn"
                >
                  Yes, Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
