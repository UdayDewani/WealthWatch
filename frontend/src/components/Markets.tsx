import { useState, useEffect, useCallback } from 'react';
import type { AssetsData, AssetItem } from '../types/assets';
import { fetchAllAssets } from '../api/assets';

// ─── helpers ────────────────────────────────────────────────────────────────

type TabId = 'commodities' | 'crypto' | 'forex' | 'etfs' | 'mutual_funds';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'commodities',  label: 'Commodities',   icon: '🏅' },
  { id: 'crypto',       label: 'Crypto',         icon: '₿' },
  { id: 'forex',        label: 'Forex',          icon: '💱' },
  { id: 'etfs',         label: 'ETFs',           icon: '📈' },
  { id: 'mutual_funds', label: 'Mutual Funds',   icon: '🏦' },
];

function fmtPrice(n: number, symbol: string): string {
  const isINR = symbol.endsWith('INR=X') || symbol.endsWith('.NS') || symbol.endsWith('.BO');
  const prefix = isINR ? '₹' : '$';
  if (n >= 1_00_00_000) return prefix + (n / 1_00_00_000).toFixed(2) + ' Cr';
  if (n >= 1_00_000)    return prefix + (n / 1_00_000).toFixed(2) + ' L';
  if (n >= 1000)        return prefix + n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  return prefix + n.toFixed(4);
}

function ChangeChip({ pct }: { pct: number }) {
  const up = pct >= 0;
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 2,
        fontSize: 12, fontWeight: 600, padding: '2px 8px',
        borderRadius: 20,
        background: up ? 'var(--green-bg)' : 'var(--red-bg)',
        color: up ? 'var(--green-text)' : 'var(--red-text)',
      }}
    >
      {up ? '▲' : '▼'} {Math.abs(pct).toFixed(2)}%
    </span>
  );
}

// ─── commodity / crypto / forex card ────────────────────────────────────────

function AssetCard({ item }: { item: AssetItem }) {
  const up = item.change_pct >= 0;
  return (
    <div className="asset-card">
      <div className="asset-card-top">
        <div className="asset-icon">{item.icon ?? item.symbol.slice(0, 2)}</div>
        <ChangeChip pct={item.change_pct} />
      </div>
      <div className="asset-name">{item.name}</div>
      {item.unit && <div className="asset-unit">{item.unit}</div>}
      {item.base && <div className="asset-unit">{item.base} → {item.quote}</div>}
      <div className="asset-price">{fmtPrice(item.price, item.symbol)}</div>
      <div style={{ fontSize: 12, color: up ? 'var(--green)' : 'var(--red)', marginTop: 2 }}>
        {up ? '+' : ''}{item.change >= 0.001 ? item.change.toFixed(item.change < 1 ? 4 : 2) : item.change.toFixed(4)}
      </div>
    </div>
  );
}

// ─── ETF / MF table row ─────────────────────────────────────────────────────

function TableSection({ items, tab }: { items: AssetItem[]; tab: TabId }) {
  if (items.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '48px 0' }}>
        <p>No data available — market may be closed or data loading.</p>
      </div>
    );
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>{tab === 'mutual_funds' ? 'Scheme' : 'ETF'}</th>
            <th>Category</th>
            <th style={{ textAlign: 'right' }}>NAV / Price</th>
            <th style={{ textAlign: 'right' }}>Change</th>
            <th style={{ textAlign: 'right' }}>% Change</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => {
            const up = item.change_pct >= 0;
            return (
              <tr key={item.symbol}>
                <td style={{ color: 'var(--text-secondary)', width: 36 }}>{i + 1}</td>
                <td>
                  <div className="stock-info">
                    <div className="stock-logo" style={{ background: '#f1f5f9', color: 'var(--text)', fontSize: 11 }}>
                      {item.symbol.split('.')[0].slice(0, 4)}
                    </div>
                    <div>
                      <div className="stock-name">{item.name}</div>
                      <div className="stock-symbol">{item.symbol}</div>
                    </div>
                  </div>
                </td>
                <td>
                  <span className="risk-chip" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
                    {item.category ?? '—'}
                  </span>
                </td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>
                  {fmtPrice(item.price, item.symbol)}
                </td>
                <td style={{ textAlign: 'right', color: up ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                  {up ? '+' : ''}{item.change.toFixed(2)}
                </td>
                <td style={{ textAlign: 'right' }}>
                  <ChangeChip pct={item.change_pct} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── main Markets page ───────────────────────────────────────────────────────

export default function Markets() {
  const [tab, setTab]       = useState<TabId>('commodities');
  const [data, setData]     = useState<AssetsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);
  const [time, setTime]     = useState('—');

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await fetchAllAssets();
      setData(d);
      setTime(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000); // refresh every 60 s
    return () => clearInterval(t);
  }, [load]);

  // ── summary stats across all categories ──────────────────────────────
  const topGainers = data
    ? [...data.commodities, ...data.crypto, ...data.forex]
        .sort((a, b) => b.change_pct - a.change_pct)
        .slice(0, 3)
    : [];

  const topLosers = data
    ? [...data.commodities, ...data.crypto, ...data.forex]
        .sort((a, b) => a.change_pct - b.change_pct)
        .slice(0, 3)
    : [];

  const activeItems: AssetItem[] = data ? data[tab] : [];
  const useCards = tab === 'commodities' || tab === 'crypto' || tab === 'forex';

  return (
    <>
      {/* Header */}
      <div className="dash-header">
        <h1>Markets</h1>
        <div className="live-status">
          <span className={`live-dot${!error ? ' active' : ' inactive'}`} />
          <span>{!error ? 'LIVE' : 'ERROR'}</span>
          <span style={{ color: 'var(--text-secondary)', fontWeight: 400, marginLeft: 4 }}>·</span>
          <span style={{ fontWeight: 400 }}>{time}</span>
          {error && <span style={{ color: 'var(--red)', fontSize: 12, marginLeft: 8 }}>{error}</span>}
          <button
            className="sort-btn"
            onClick={load}
            style={{ marginLeft: 12, padding: '4px 12px', fontSize: 12 }}
            id="markets-refresh-btn"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Top gainers / losers strip */}
      {!loading && data && (
        <div className="markets-strip">
          <div className="strip-group">
            <div className="strip-label">🚀 Top Gainers</div>
            <div className="strip-chips">
              {topGainers.map(a => (
                <span key={a.symbol} className="strip-chip gain">
                  {a.icon ?? ''} {a.name} <strong>+{a.change_pct.toFixed(2)}%</strong>
                </span>
              ))}
            </div>
          </div>
          <div className="strip-group">
            <div className="strip-label">📉 Top Losers</div>
            <div className="strip-chips">
              {topLosers.map(a => (
                <span key={a.symbol} className="strip-chip loss">
                  {a.icon ?? ''} {a.name} <strong>{a.change_pct.toFixed(2)}%</strong>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="markets-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`markets-tab${tab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
            id={`tab-${t.id}`}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
            {data && (
              <span className="tab-count">{data[t.id].length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="empty-state" style={{ padding: '80px 0' }}>
          <h3>Loading market data…</h3>
          <p style={{ marginTop: 8, color: 'var(--text-secondary)' }}>
            Fetching live prices from Yahoo Finance. This may take a few seconds.
          </p>
        </div>
      ) : error && !data ? (
        <div className="empty-state" style={{ padding: '80px 0' }}>
          <h3>Could not load market data</h3>
          <p style={{ marginTop: 8, marginBottom: 16 }}>{error}</p>
          <button className="btn-primary" onClick={load}>Retry</button>
        </div>
      ) : (
        <div className="card">
          <div className="section-header" style={{ marginBottom: 20 }}>
            <h2>
              {TABS.find(t => t.id === tab)?.icon}{' '}
              {TABS.find(t => t.id === tab)?.label}
            </h2>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {activeItems.length} instruments · auto-refreshes every 60s
            </span>
          </div>

          {useCards ? (
            activeItems.length === 0 ? (
              <div className="empty-state" style={{ padding: '48px 0' }}>
                <p>No data available — market may be closed or loading.</p>
              </div>
            ) : (
              <div className="assets-grid">
                {activeItems.map(item => (
                  <AssetCard key={item.symbol} item={item} />
                ))}
              </div>
            )
          ) : (
            <TableSection items={activeItems} tab={tab} />
          )}
        </div>
      )}
    </>
  );
}
