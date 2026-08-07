import type { Analysis } from '../types/market';

interface Props {
  analysis?: Analysis;
}

export default function SummaryCard({ analysis }: Props) {
  const condition = analysis?.nifty?.condition || 'neutral';
  const badgeClass = condition === 'bullish' ? 'badge bullish' : condition === 'bearish' ? 'badge bearish' : 'badge neutral';

  return (
    <div className="summary-card">
      <div>
        <span className={badgeClass} style={{ marginRight: 12 }}>{condition.toUpperCase()}</span>
        <span className="summary-text">{analysis?.summary || 'Waiting for AI analysis...'}</span>
      </div>
      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Powered by AI Agent</span>
    </div>
  );
}
