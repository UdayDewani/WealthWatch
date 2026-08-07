import type { Analysis } from '../types/market';

interface Props {
  open: boolean;
  index: 'nifty' | 'sensex' | 'niftybank' | 'niftyit' | null;
  analysis?: Analysis;
  onClose: () => void;
}

const explanations: Record<string, { label: string; items: { point: string; detail: string; pos: boolean }[] }> = {
  nifty: {
    label: 'NIFTY 50',
    items: [
      { point: 'FII Inflows', detail: 'Foreign institutional investors have been net buyers for the last 5 sessions, adding ₹2,340 Cr.', pos: true },
      { point: 'Banking Sector', detail: 'Nifty Bank index up 1.2%, led by HDFC Bank and ICICI Bank on strong Q3 earnings.', pos: true },
      { point: 'Global Cues', detail: 'US markets closed higher, Asian markets trading green, positive global sentiment.', pos: true },
      { point: 'Oil Prices', detail: 'Crude oil remains stable at $78/bbl, easing inflation concerns for India.', pos: true },
      { point: 'News Sentiment', detail: 'Positive budget expectations and strong GST collections boosting investor confidence.', pos: true },
    ],
  },
  sensex: {
    label: 'SENSEX',
    items: [
      { point: 'IT Sector Rebound', detail: 'TCS and Infosys recovering after recent correction, contributing to index gains.', pos: true },
      { point: 'Auto Sales', detail: 'Maruti and Tata Motors reported strong monthly sales numbers.', pos: true },
      { point: 'Rupee Strength', detail: 'INR stable at 83.5/USD, reducing volatility for FII flows.', pos: true },
      { point: 'Metal Stocks', detail: 'Hindalco and Tata Steel up on China demand recovery hopes.', pos: true },
      { point: 'Technical Factors', detail: 'Sensex broke above 77,000 resistance level with strong volume support.', pos: true },
    ],
  },
  niftybank: {
    label: 'NIFTY BANK',
    items: [
      { point: 'Credit Growth', detail: 'System-wide credit growth remains robust at 16% YoY, boosting NIM projections.', pos: true },
      { point: 'Asset Quality', detail: 'Net NPA ratios across major private and public banks are at multi-year lows.', pos: true },
      { point: 'PSU Banks', detail: 'SBI and Bank of Baroda show strong institutional support on valuation comfort.', pos: true },
      { point: 'Interest Rates', detail: 'RBI rate-cut expectations in coming quarters supportive of bank margins.', pos: true }
    ],
  },
  niftyit: {
    label: 'NIFTY IT',
    items: [
      { point: 'Deal Pipelines', detail: 'Strong deal pipelines from US and Europe provide a long-term buffer.', pos: true },
      { point: 'Currency Tailwind', detail: 'A stable USD-INR exchange rate supports profit margins of export-driven IT firms.', pos: true },
      { point: 'Valuation Support', detail: 'Recent IT corrections have brought multiples closer to historical averages.', pos: true },
      { point: 'AI Integration', detail: 'Enterprise spending shifting towards AI and cloud projects, benefiting Indian tech majors.', pos: true }
    ],
  }
};

export default function Drawer({ open, index, analysis, onClose }: Props) {
  const data = index ? explanations[index] : null;
  const indexAnalysis = index && analysis ? analysis[index] : null;
  const condition = indexAnalysis?.condition || 'neutral';
  const isBullish = condition === 'bullish';
  const isBearish = condition === 'bearish';
  const displayCondition = isBullish ? 'Bullish' : isBearish ? 'Bearish' : 'Neutral';

  return (
    <>
      <div className={`drawer-overlay${open ? ' open' : ''}`} onClick={onClose} />
      <div className={`drawer${open ? ' open' : ''}`}>
        <div className="drawer-header">
          <h3 id="drawerTitle">{data?.label || ''} — {displayCondition} Outlook</h3>
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>
        <div className="drawer-body">
          <div className="ai-tag" style={{ marginBottom: 16 }}>🤖 Powered by AI Agent</div>
          
          {indexAnalysis?.reasoning && (
            <div style={{
              background: 'var(--nav-bg)',
              borderRadius: '8px',
              padding: '16px',
              marginBottom: '20px',
              borderLeft: '4px solid var(--primary)',
              fontSize: '13px'
            }}>
              <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text)' }}>AI Analysis Summary</strong>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{indexAnalysis.reasoning}</span>
            </div>
          )}

          {data?.items.map((item, i) => (
            <div className="explanation-item" key={i}>
              <span className={`dot ${item.pos ? 'pos' : 'neg'}`} />
              <div className="text">
                <div className="label">{item.point}</div>
                <div className="desc">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
