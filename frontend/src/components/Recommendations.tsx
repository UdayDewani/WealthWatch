import { useMemo } from 'react';
import type { Recommendation, MarketData } from '../types/market';

const FALLBACK_RECS: Recommendation[] = [
  { stock: 'Reliance Industries Ltd.', symbol: 'RELIANCE', action: 'buy', reason: 'Strong consolidation near support levels. Technical indicators point to a strong upward breakout soon.', confidence: 92 },
  { stock: 'HDFC Bank Ltd.', symbol: 'HDFCBANK', action: 'buy', reason: 'Healthy credit growth and attractive valuations post-merger consolidate its leadership stance.', confidence: 88 },
  { stock: 'Infosys Ltd.', symbol: 'INFY', action: 'hold', reason: 'IT spending remains cautious in global markets, but the strong deal pipeline provides long term support.', confidence: 72 },
  { stock: 'Tata Motors Passenger Vehicles Ltd.', symbol: 'TATAMOTORS', action: 'buy', reason: 'Strong EV order books and robust domestic commercial vehicle segments support positive cash flows.', confidence: 85 }
];

interface Props {
  marketData: MarketData | null;
}

export default function Recommendations({ marketData }: Props) {
  const activeRecs = useMemo(() => {
    if (marketData?.analysis?.recommendations && marketData.analysis.recommendations.length > 0) {
      return marketData.analysis.recommendations;
    }
    return FALLBACK_RECS;
  }, [marketData]);

  return (
    <>
      <div className="dash-header">
        <h1>AI Recommendations</h1>
        <span className="badge" style={{ background: 'var(--primary-light)', color: 'var(--primary)', fontSize: 11 }}>Powered by Gemini AI</span>
      </div>
      <div className="rec-grid">
        {activeRecs.map((r, idx) => (
          <div className="rec-card" key={`${r.symbol}-${idx}`}>
            <div className="top">
              <div>
                <div className="stock">{r.stock}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.symbol}</div>
              </div>
              <span className={`action ${r.action}`}>{r.action.toUpperCase()}</span>
            </div>
            <div className="reason">{r.reason}</div>
            <div>
              <div className="confidence-label">
                <span>AI Confidence</span>
                <span>{r.confidence}%</span>
              </div>
              <div className="confidence-bar">
                <div className="fill" style={{
                  width: `${r.confidence}%`,
                  background: r.confidence >= 85 ? 'var(--green)' : r.confidence >= 70 ? '#eab308' : 'var(--primary)'
                }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
