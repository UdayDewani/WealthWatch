const navItems = [
  { page: 'dashboard', label: 'Dashboard',        icon: GridIcon },
  { page: 'clients',   label: 'Clients',           icon: UsersIcon },
  { page: 'portfolio', label: 'Portfolio',         icon: PieIcon },
  { page: 'recommend', label: 'AI Recommendations', icon: StarIcon, tag: 'Beta' },
];

export default function Sidebar({ active, onNavigate }: { active: string; onNavigate: (p: string) => void }) {
  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-icon">W</div>
        <span className="logo-text">WealthWatch</span>
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
        <div className="avatar">WM</div>
        <div>
          <div className="avatar-name">Wealth Manager</div>
          <div className="avatar-role">Portfolio Advisor</div>
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

function UsersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
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
