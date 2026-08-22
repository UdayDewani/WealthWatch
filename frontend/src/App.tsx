import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Clients from './components/Clients';
import Markets from './components/Markets';

export default function App() {
  const [page, setPage] = useState('dashboard');

  return (
    <div className="app-layout">
      <Sidebar active={page} onNavigate={setPage} />
      <div className="main">
        {page === 'dashboard' && <Dashboard onAnalysis={() => {}} />}
        {page === 'markets'   && <Markets />}
        {page === 'clients'   && <Clients />}
      </div>
    </div>
  );
}
