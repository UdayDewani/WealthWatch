import { useState, useEffect } from 'react';
import type { Client, ClientCreate, ClientUpdate } from '../api/clients';

interface Props {
  open: boolean;
  client: Client | null; // null = add mode, Client = edit mode
  onClose: () => void;
  onSave: (data: ClientCreate | ClientUpdate) => Promise<void>;
}

const EMPTY: ClientCreate = {
  name: '',
  email: '',
  phone: '',
  pan: '',
  risk_profile: 'moderate',
  aum: 0,
  joined_date: new Date().toISOString().split('T')[0],
  notes: '',
};

export default function ClientModal({ open, client, onClose, onSave }: Props) {
  const [form, setForm] = useState<ClientCreate>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync form when modal opens
  useEffect(() => {
    if (open) {
      setForm(client ? { ...client } : { ...EMPTY });
      setError(null);
    }
  }, [open, client]);

  const set = (field: keyof ClientCreate, value: string | number) =>
    setForm(prev => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.phone.trim()) {
      setError('Name, email, and phone are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{client ? 'Edit Client' : 'Add New Client'}</h3>
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>

        <form className="modal-body" onSubmit={handleSubmit}>
          {error && <div className="modal-error">{error}</div>}

          <div className="form-row">
            <div className="form-group">
              <label>Full Name *</label>
              <input
                className="form-input"
                value={form.name}
                onChange={e => set('name', e.target.value)}
                placeholder="Rajesh Sharma"
                required
              />
            </div>
            <div className="form-group">
              <label>Email *</label>
              <input
                className="form-input"
                type="email"
                value={form.email}
                onChange={e => set('email', e.target.value)}
                placeholder="rajesh@example.com"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Phone *</label>
              <input
                className="form-input"
                value={form.phone}
                onChange={e => set('phone', e.target.value)}
                placeholder="+91 98765 43210"
                required
              />
            </div>
            <div className="form-group">
              <label>PAN Number</label>
              <input
                className="form-input"
                value={form.pan}
                onChange={e => set('pan', e.target.value.toUpperCase())}
                placeholder="ABCDE1234F"
                maxLength={10}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Risk Profile</label>
              <select
                className="form-input"
                value={form.risk_profile}
                onChange={e => set('risk_profile', e.target.value)}
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
            <div className="form-group">
              <label>AUM (₹)</label>
              <input
                className="form-input"
                type="number"
                min={0}
                value={form.aum}
                onChange={e => set('aum', parseFloat(e.target.value) || 0)}
                placeholder="5000000"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Client Since</label>
              <input
                className="form-input"
                type="date"
                value={form.joined_date}
                onChange={e => set('joined_date', e.target.value)}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 4 }}>
            <label>Notes</label>
            <textarea
              className="form-input"
              rows={3}
              value={form.notes}
              onChange={e => set('notes', e.target.value)}
              placeholder="Investment goals, preferences, special instructions..."
              style={{ resize: 'vertical' }}
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Saving...' : client ? 'Save Changes' : 'Add Client'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
