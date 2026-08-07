const navItems = [
  { page: 'dashboard', label: 'Dashboard', icon: GridIcon },
  { page: 'portfolio', label: 'Portfolio', icon: PieIcon },
  { page: 'recommend', label: 'AI Recommendations', icon: StarIcon, tag: 'Beta' },
];

export default function Sidebar({ active, onNavigate }: { active: string; onNavigate: (p: string) => void }) {
  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-icon">S</div>
        <span className="logo-text">StockSense</span>
      </div>
      <nav className="nav">
        {navItems.map(({ page, label, icon: Icon, tag }) => (
          <div
            key={page}
            className={`nav-item${active === page ? ' active' : ''}`}
            onClick={() => onNavigate(page)}
          >
            <span className="icon"><Icon /></span>
            <span>{label}</span>
            {tag && <span className="tag">{tag}</span>}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="avatar">AK</div>
        <div>
          <div className="avatar-name">Aniket</div>
          <div className="avatar-role">Trader</div>
        </div>
      </div>
    </aside>
  );
}

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/>
      <rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>
    </svg>
  );
}

function PieIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
    </svg>
  );
}

function StarIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2l2.4 7.2L22 9.6l-5.6 4.8 1.6 7.6L12 18.4 6 22l1.6-7.6L2 9.6l7.6-.4L12 2z"/>
    </svg>
  );
}
