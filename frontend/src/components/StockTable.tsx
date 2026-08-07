import { useMemo, useState } from 'react';
import type { Stock } from '../types/market';

const FALLBACK_N50: Stock[] = [
  { rank: 1, name: 'Reliance Industries Ltd.', symbol: 'RELIANCE', price: 2890.45, change_pct: 1.23, volume: 12500000 },
  { rank: 2, name: 'Tata Consultancy Services Ltd.', symbol: 'TCS', price: 3892.10, change_pct: -0.45, volume: 8900000 },
  { rank: 3, name: 'HDFC Bank Ltd.', symbol: 'HDFCBANK', price: 1678.30, change_pct: 0.89, volume: 15200000 },
  { rank: 4, name: 'Infosys Ltd.', symbol: 'INFY', price: 1520.65, change_pct: -0.67, volume: 9800000 },
  { rank: 5, name: 'ICICI Bank Ltd.', symbol: 'ICICIBANK', price: 1123.40, change_pct: 1.56, volume: 11000000 },
  { rank: 6, name: 'Bharti Airtel Ltd.', symbol: 'BHARTIARTL', price: 1345.20, change_pct: 0.34, volume: 7200000 },
  { rank: 7, name: 'State Bank of India', symbol: 'SBIN', price: 834.55, change_pct: -0.23, volume: 18400000 },
  { rank: 8, name: 'ITC Ltd.', symbol: 'ITC', price: 445.30, change_pct: 0.78, volume: 14500000 },
  { rank: 9, name: 'Hindustan Unilever Ltd.', symbol: 'HINDUNILVR', price: 2345.60, change_pct: -0.89, volume: 5600000 },
  { rank: 10, name: 'Larsen & Toubro Ltd.', symbol: 'LT', price: 3456.75, change_pct: 1.12, volume: 6800000 },
];

const FALLBACK_BANK: Stock[] = [
  { rank: 1, name: 'HDFC Bank Ltd.', symbol: 'HDFCBANK', price: 1678.30, change_pct: 0.89, volume: 15200000 },
  { rank: 2, name: 'ICICI Bank Ltd.', symbol: 'ICICIBANK', price: 1123.40, change_pct: 1.56, volume: 11000000 },
  { rank: 3, name: 'State Bank of India', symbol: 'SBIN', price: 834.55, change_pct: -0.23, volume: 18400000 },
  { rank: 4, name: 'Axis Bank Ltd.', symbol: 'AXISBANK', price: 1089.30, change_pct: 0.34, volume: 11300000 },
  { rank: 5, name: 'Kotak Mahindra Bank Ltd.', symbol: 'KOTAKBANK', price: 1890.30, change_pct: -0.56, volume: 5900000 },
  { rank: 6, name: 'IndusInd Bank Ltd.', symbol: 'INDUSINDBK', price: 1450.90, change_pct: 1.10, volume: 4200000 },
  { rank: 7, name: 'Federal Bank Ltd.', symbol: 'FEDERALBNK', price: 165.30, change_pct: -0.15, volume: 3800000 },
  { rank: 8, name: 'IDFC First Bank Ltd.', symbol: 'IDFCFIRSTB', price: 78.50, change_pct: 0.25, volume: 7500000 },
];

interface Props {
  stocks?: {
    nifty50: Stock[];
    niftybank: Stock[];
  };
}

export default function StockTable({ stocks }: Props) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('rank');
  const [indexType, setIndexType] = useState<'nifty50' | 'niftybank'>('nifty50');

  // Determine current active list
  const activeStocks = useMemo(() => {
    if (stocks) {
      if (indexType === 'nifty50' && stocks.nifty50 && stocks.nifty50.length > 0) {
        return stocks.nifty50;
      }
      if (indexType === 'niftybank' && stocks.niftybank && stocks.niftybank.length > 0) {
        return stocks.niftybank;
      }
    }
    return indexType === 'nifty50' ? FALLBACK_N50 : FALLBACK_BANK;
  }, [stocks, indexType]);

  const filtered = useMemo(() => {
    let list = [...activeStocks].filter(s =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.symbol.toLowerCase().includes(search.toLowerCase())
    );

    switch (sort) {
      case 'change_desc': list.sort((a, b) => b.change_pct - a.change_pct); break;
      case 'change_asc': list.sort((a, b) => a.change_pct - b.change_pct); break;
      case 'price_desc': list.sort((a, b) => b.price - a.price); break;
      case 'price_asc': list.sort((a, b) => a.price - b.price); break;
      default: list.sort((a, b) => a.rank - b.rank);
    }
    return list;
  }, [activeStocks, search, sort]);

  const fmtVol = (v: number) => v >= 1e7 ? (v / 1e7).toFixed(1) + 'Cr' : v >= 1e5 ? (v / 1e5).toFixed(1) + 'L' : v.toLocaleString();

  return (
    <div className="card">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <h2>Constituent Stocks</h2>
          <div style={{ display: 'flex', background: 'var(--nav-bg)', borderRadius: '8px', padding: '2px' }}>
            <button 
              onClick={() => setIndexType('nifty50')}
              style={{
                border: 'none',
                background: indexType === 'nifty50' ? 'var(--card-bg)' : 'transparent',
                color: indexType === 'nifty50' ? 'var(--primary)' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 12,
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                boxShadow: indexType === 'nifty50' ? 'var(--shadow)' : 'none',
                transition: 'all 0.15s'
              }}
            >
              Nifty 50
            </button>
            <button 
              onClick={() => setIndexType('niftybank')}
              style={{
                border: 'none',
                background: indexType === 'niftybank' ? 'var(--card-bg)' : 'transparent',
                color: indexType === 'niftybank' ? 'var(--primary)' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: 12,
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                boxShadow: indexType === 'niftybank' ? 'var(--shadow)' : 'none',
                transition: 'all 0.15s'
              }}
            >
              Nifty Bank
            </button>
          </div>
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          {indexType === 'nifty50' ? '50 Stocks' : '12 Stocks'}
        </span>
      </div>
      <div className="table-toolbar">
        <div className="search-box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
          </svg>
          <input type="text" placeholder="Search stocks..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="sort-btn" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="rank">Sort: Rank</option>
          <option value="change_desc">% Change ↓</option>
          <option value="change_asc">% Change ↑</option>
          <option value="price_desc">Price ↓</option>
          <option value="price_asc">Price ↑</option>
        </select>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 32 }}>#</th>
              <th>Stock</th>
              <th style={{ textAlign: 'right' }}>Price</th>
              <th style={{ textAlign: 'right' }}>% Change</th>
              <th style={{ textAlign: 'right' }}>Volume</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={`${s.symbol}-${s.rank}`}>
                <td className="rank">{s.rank}</td>
                <td>
                  <div className="stock-info">
                    <div className="stock-logo">{s.symbol.slice(0, 2)}</div>
                    <div>
                      <div className="stock-name">{s.name}</div>
                      <div className="stock-symbol">{s.symbol}</div>
                    </div>
                  </div>
                </td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>{s.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                <td style={{ textAlign: 'right', color: s.change_pct >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                  {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                </td>
                <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{fmtVol(s.volume)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
