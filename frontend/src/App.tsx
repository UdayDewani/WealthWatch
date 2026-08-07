import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Portfolio from './components/Portfolio';
import Clients from './components/Clients';
import Recommendations from './components/Recommendations';
import type { MarketData } from './types/market';

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [marketData, setMarketData] = useState<MarketData | null>(null);

  return (
    <div className="app-layout">
      <Sidebar active={page} onNavigate={setPage} />
      <div className="main">
        {page === 'dashboard' && (
          <Dashboard
            onAnalysis={() => {}}
            onMarketData={setMarketData}
          />
        )}
        {page === 'clients'   && <Clients />}
        {page === 'portfolio' && <Portfolio />}
        {page === 'recommend' && <Recommendations marketData={marketData} />}
      </div>
    </div>
  );
}
