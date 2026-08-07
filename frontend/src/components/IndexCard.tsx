import { useMemo } from 'react';
import type { IndexData, IndexAnalysis } from '../types/market';

interface Props {
  data: IndexData;
  label: string;
  iconLabel: string;
  analysis?: IndexAnalysis;
  onClick: () => void;
}

export default function IndexCard({ data, label, iconLabel, analysis, onClick }: Props) {
  const isUp = data.change >= 0;
  const condition = analysis?.condition || (isUp ? 'bullish' : 'bearish');

  const sparkPoints = useMemo(() => {
    const pts: number[] = [];
    for (let i = 0; i < 20; i++) {
      const base = data.price;
      pts.push(base + (Math.random() - 0.5) * base * 0.02);
    }
    return pts;
  }, [data.price]);

  const min = Math.min(...sparkPoints);
  const max = Math.max(...sparkPoints);
  const range = max - min || 1;

  const pathD = sparkPoints
    .map((p, i) => {
      const x = (i / (sparkPoints.length - 1)) * 120;
      const y = 28 - ((p - min) / range) * 24;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const badgeClass = condition === 'bullish' ? 'badge bullish' : condition === 'bearish' ? 'badge bearish' : 'badge neutral';

  return (
    <div className="index-card" onClick={onClick}>
      <div className="top-row">
        <div className="name-section">
          <div className="index-icon">{iconLabel}</div>
          <div className="index-name">{label}</div>
        </div>
        <span className={badgeClass}>{condition.toUpperCase()}</span>
      </div>
      <div className="price">{data.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
      <div className="change-row">
        <span className={`change ${isUp ? 'pos' : 'neg'}`}>
          {isUp ? '+' : ''}{data.change.toFixed(2)} ( {isUp ? '+' : ''}{data.change_pct.toFixed(2)}% )
        </span>
      </div>
      <div className="sparkline">
        <svg viewBox="0 0 120 28" width="100%" height="28">
          <path d={pathD} fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
    </div>
  );
}
