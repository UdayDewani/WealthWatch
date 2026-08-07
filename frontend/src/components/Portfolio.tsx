const holdings = [
  { name: 'Reliance Industries', symbol: 'RELIANCE', qty: 50, avgCost: 2670, ltp: 2890.45, pnl: 11022.50, returns: 8.26 },
  { name: 'Tata Consultancy Services', symbol: 'TCS', qty: 30, avgCost: 3750, ltp: 3892.10, pnl: 4263.00, returns: 3.79 },
  { name: 'HDFC Bank', symbol: 'HDFCBANK', qty: 80, avgCost: 1620, ltp: 1678.30, pnl: 4664.00, returns: 3.60 },
  { name: 'Infosys', symbol: 'INFY', qty: 60, avgCost: 1480, ltp: 1520.65, pnl: 2439.00, returns: 2.75 },
  { name: 'ICICI Bank', symbol: 'ICICIBANK', qty: 100, avgCost: 1050, ltp: 1123.40, pnl: 7340.00, returns: 6.99 },
  { name: 'Bharti Airtel', symbol: 'BHARTIARTL', qty: 40, avgCost: 1280, ltp: 1345.20, pnl: 2608.00, returns: 5.09 },
  { name: 'ITC', symbol: 'ITC', qty: 150, avgCost: 420, ltp: 445.30, pnl: 3795.00, returns: 6.02 },
  { name: 'Larsen & Toubro', symbol: 'LT', qty: 25, avgCost: 3300, ltp: 3456.75, pnl: 3918.75, returns: 4.75 },
];

const allocation = [
  { name: 'Banking', pct: 30, color: '#2563eb' },
  { name: 'IT', pct: 22, color: '#7c3aed' },
  { name: 'Energy', pct: 15, color: '#059669' },
  { name: 'Auto', pct: 12, color: '#d97706' },
  { name: 'FMCG', pct: 11, color: '#dc2626' },
  { name: 'Others', pct: 10, color: '#64748b' },
];

export default function Portfolio() {
  const totalValue = holdings.reduce((s, h) => s + h.ltp * h.qty, 0);
  const totalCost = holdings.reduce((s, h) => s + h.avgCost * h.qty, 0);
  const totalPnl = totalValue - totalCost;
  const totalReturns = (totalPnl / totalCost) * 100;

  const fmt = (n: number) => '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2 });

  let cumulativeAngle = 0;
  const slices = allocation.map(a => {
    const angle = (a.pct / 100) * 360;
    const startAngle = cumulativeAngle;
    cumulativeAngle += angle;
    const startRad = (startAngle - 90) * (Math.PI / 180);
    const endRad = (startAngle + angle - 90) * (Math.PI / 180);
    const x1 = 90 + 80 * Math.cos(startRad);
    const y1 = 90 + 80 * Math.sin(startRad);
    const x2 = 90 + 80 * Math.cos(endRad);
    const y2 = 90 + 80 * Math.sin(endRad);
    const large = angle > 180 ? 1 : 0;
    const d = `M90,90 L${x1.toFixed(1)},${y1.toFixed(1)} A80,80 0 ${large},1 ${x2.toFixed(1)},${y2.toFixed(1)} Z`;
    return { ...a, d };
  });

  return (
    <>
      <div className="dash-header">
        <h1>Portfolio</h1>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Last updated: Today 3:45 PM</span>
      </div>
      <div className="portfolio-summary">
        <div className="stat-card">
          <div className="label">Total Value</div>
          <div className="value">{fmt(totalValue)}</div>
          <div className="sub" style={{ color: 'var(--green)' }}>+{fmt(totalPnl)} ({totalReturns.toFixed(2)}%)</div>
        </div>
        <div className="stat-card">
          <div className="label">Today's P&L</div>
          <div className="value" style={{ color: 'var(--green)' }}>+₹8,240</div>
          <div className="sub" style={{ color: 'var(--green)' }}>+0.67%</div>
        </div>
        <div className="stat-card">
          <div className="label">Total Returns</div>
          <div className="value" style={{ color: 'var(--green)' }}>+{fmt(totalPnl)}</div>
          <div className="sub" style={{ color: 'var(--green)' }}>+{totalReturns.toFixed(2)}%</div>
        </div>
      </div>

      <div className="card">
        <div className="section-header"><h2>Holdings</h2></div>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Stock</th>
                <th style={{ textAlign: 'right' }}>Qty</th>
                <th style={{ textAlign: 'right' }}>Avg Cost</th>
                <th style={{ textAlign: 'right' }}>LTP</th>
                <th style={{ textAlign: 'right' }}>P&L</th>
                <th style={{ textAlign: 'right' }}>Returns</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map(h => (
                <tr key={h.symbol}>
                  <td>
                    <div className="stock-info">
                      <div className="stock-logo">{h.symbol.slice(0, 2)}</div>
                      <div>
                        <div className="stock-name">{h.name}</div>
                        <div className="stock-symbol">{h.symbol}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>{h.qty}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(h.avgCost)}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600 }}>{fmt(h.ltp)}</td>
                  <td style={{ textAlign: 'right', color: h.pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {h.pnl >= 0 ? '+' : ''}{fmt(h.pnl)}
                  </td>
                  <td style={{ textAlign: 'right', color: h.returns >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {h.returns >= 0 ? '+' : ''}{h.returns.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="section-header"><h2>Allocation</h2></div>
        <div className="pie-container">
          <div className="pie-chart">
            <svg viewBox="0 0 180 180">
              {slices.map((s, i) => (
                <path key={i} d={s.d} fill={s.color} stroke="#fff" strokeWidth="2" />
              ))}
            </svg>
            <div className="pie-center">
              <div className="val">100%</div>
              <div className="lbl">Allocated</div>
            </div>
          </div>
          <div className="pie-legend">
            {allocation.map(a => (
              <div className="pie-legend-item" key={a.name}>
                <span className="swatch" style={{ background: a.color }} />
                <span className="lbl">{a.name}</span>
                <span className="pct">{a.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
