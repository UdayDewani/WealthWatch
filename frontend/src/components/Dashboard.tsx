import { useState, useEffect, useCallback } from 'react';
import type { MarketData } from '../types/market';
import { fetchMarketOverview, createWebSocket } from '../api/market';
import IndexCard from './IndexCard';
import StockTable from './StockTable';
import SummaryCard from './SummaryCard';
import Drawer from './Drawer';

interface Props {
  onAnalysis: (a: MarketData['analysis']) => void;
  onMarketData?: (d: MarketData) => void;
}

const FALLBACK_MARKET_DATA: MarketData = {
  indices: {
    nifty: { price: 23450.30, change: 125.60, change_pct: 0.54, volume: 2300000 },
    sensex: { price: 77215.80, change: 412.30, change_pct: 0.54, volume: 1100000 },
    niftybank: { price: 51200.50, change: 320.10, change_pct: 0.63, volume: 1500000 },
    niftyit: { price: 38500.20, change: -150.40, change_pct: -0.39, volume: 800000 },
  },
  stocks: {
    nifty50: [],
    niftybank: []
  },
  nifty: { price: 23450.30, change: 125.60, change_pct: 0.54, volume: 2300000 },
  sensex: { price: 77215.80, change: 412.30, change_pct: 0.54, volume: 1100000 },
  news: [],
  timestamp: new Date().toISOString(),
};

export default function Dashboard({ onAnalysis, onMarketData }: Props) {
  const [data, setData] = useState<MarketData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawerIndex, setDrawerIndex] = useState<'nifty' | 'sensex' | 'niftybank' | 'niftyit' | null>(null);
  const [time, setTime] = useState('—');

  const updateFromServer = useCallback(async () => {
    setError(null);
    try {
      const d = await fetchMarketOverview(25000);
      setData(prev => ({ ...prev, ...d, analysis: prev?.analysis || d.analysis }));
      if (onMarketData) onMarketData(d);
      setTime(new Date().toLocaleTimeString());
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Request failed';
      setError(msg);
      if (!data) setData(FALLBACK_MARKET_DATA);
    } finally {
      setLoading(false);
    }
  }, [data, onMarketData]);

  useEffect(() => {
    updateFromServer();
    const interval = setInterval(updateFromServer, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const ws = createWebSocket();
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        setData(prev => prev ? { ...prev, ...msg } : msg);
        if (onMarketData) onMarketData(msg);
        setTime(new Date().toLocaleTimeString());
        if (msg.analysis) onAnalysis(msg.analysis);
      } catch { /* ignore malformed messages */ }
    };
    ws.onerror = () => setError('WebSocket connection failed');
    return () => ws.close();
  }, [onAnalysis, onMarketData]);

  if (loading && !data) {
    return (
      <div className="empty-state">
        <h3>Loading market data...</h3>
        <p style={{ marginTop: 8 }}>Fetching latest market indices and stocks</p>
      </div>
    );
  }

  // Fallback to indices object or top-level nifty
  const niftyData = data?.indices?.nifty || data?.nifty || FALLBACK_MARKET_DATA.nifty;
  const sensexData = data?.indices?.sensex || data?.sensex || FALLBACK_MARKET_DATA.sensex;
  const bankData = data?.indices?.niftybank || FALLBACK_MARKET_DATA.indices!.niftybank;
  const itData = data?.indices?.niftyit || FALLBACK_MARKET_DATA.indices!.niftyit;


  if (!niftyData) {
    return (
      <div className="empty-state">
        <h3>Unable to load market data</h3>
        <p style={{ marginTop: 8, marginBottom: 16 }}>{error || 'Check that the backend server is running'}</p>
        <button className="sort-btn" onClick={updateFromServer}>Retry</button>
      </div>
    );
  }

  return (
    <>
      <div className="dash-header">
        <h1>Dashboard</h1>
        <div className="live-status">
          <span className={`live-dot${!error ? ' active' : ' inactive'}`} />
          <span>{!error ? 'LIVE' : 'ERROR'}</span>
          <span style={{ color: 'var(--text-secondary)', fontWeight: 400, marginLeft: 4 }}>·</span>
          <span style={{ fontWeight: 400 }}>{time}</span>
          {error && <span style={{ color: 'var(--red)', fontSize: 12, marginLeft: 8 }}>{error}</span>}
        </div>
      </div>

      <div className="index-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '24px' }}>
        <IndexCard
          data={niftyData}
          label="NIFTY 50"
          iconLabel="N50"
          analysis={data?.analysis?.nifty}
          onClick={() => setDrawerIndex('nifty')}
        />
        <IndexCard
          data={sensexData}
          label="SENSEX"
          iconLabel="SEN"
          analysis={data?.analysis?.sensex}
          onClick={() => setDrawerIndex('sensex')}
        />
        <IndexCard
          data={bankData}
          label="NIFTY BANK"
          iconLabel="BNK"
          analysis={data?.analysis?.niftybank}
          onClick={() => setDrawerIndex('niftybank')}
        />
        <IndexCard
          data={itData}
          label="NIFTY IT"
          iconLabel="IT"
          analysis={data?.analysis?.niftyit}
          onClick={() => setDrawerIndex('niftyit')}
        />
      </div>

      <SummaryCard analysis={data?.analysis} />
      <StockTable stocks={data?.stocks} />

      <Drawer
        open={drawerIndex !== null}
        index={drawerIndex}
        analysis={data?.analysis}
        onClose={() => setDrawerIndex(null)}
      />
    </>
  );
}
