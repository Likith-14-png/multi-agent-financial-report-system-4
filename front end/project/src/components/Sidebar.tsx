import { useApp } from '@/lib/AppContext';
import { Icon } from '@/components/Icon';
import type { PageId } from '@/lib/types';

const NAV: { id: PageId; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
  { id: 'workspace', label: 'Research Workspace', icon: 'FolderPlus' },
  { id: 'chat', label: 'AI Chat', icon: 'MessageSquare' },
  { id: 'comparison', label: 'Comparison', icon: 'GitCompare' },
  { id: 'redflags', label: 'Red Flags', icon: 'Flag' },
  { id: 'reports', label: 'Reports', icon: 'FileBarChart' },
  { id: 'history', label: 'History', icon: 'History' },
  { id: 'settings', label: 'Settings', icon: 'Settings' },
];

export function Sidebar() {
  const { page, setPage, sidebarOpen, setSidebarOpen } = useApp();

  const go = (p: PageId) => {
    setPage(p);
    setSidebarOpen(false);
  };

  return (
    <>
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      <aside
        className={`fixed lg:sticky top-0 left-0 h-screen w-64 bg-surface border-r border-base z-40 flex flex-col transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-5 border-b border-base shrink-0">
          <div className="w-9 h-9 rounded-xl gradient-brand flex items-center justify-center shrink-0">
            <Icon name="BrainCircuit" size={20} className="text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-primary tracking-tight truncate">FinSight AI</h1>
            <p className="text-[11px] text-tertiary truncate">Financial Research Platform</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
          <p className="px-3 mb-2 text-[11px] font-semibold text-tertiary uppercase tracking-wider">Main</p>
          {NAV.slice(0, 7).map((item) => {
            const active = page === item.id;
            return (
              <button
                key={item.id}
                onClick={() => go(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                  active
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                    : 'text-secondary hover:bg-subtle hover:text-primary'
                }`}
              >
                <Icon
                  name={item.icon}
                  size={19}
                  className={active ? 'text-brand-600 dark:text-brand-400' : 'text-tertiary group-hover:text-secondary'}
                />
                {item.label}
                {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-500" />}
              </button>
            );
          })}
          <p className="px-3 mt-5 mb-2 text-[11px] font-semibold text-tertiary uppercase tracking-wider">Account</p>
          {NAV.slice(7).map((item) => {
            const active = page === item.id;
            return (
              <button
                key={item.id}
                onClick={() => go(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                  active
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                    : 'text-secondary hover:bg-subtle hover:text-primary'
                }`}
              >
                <Icon
                  name={item.icon}
                  size={19}
                  className={active ? 'text-brand-600 dark:text-brand-400' : 'text-tertiary group-hover:text-secondary'}
                />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Agent status mini */}
        <div className="p-3 shrink-0">
          <div className="rounded-xl bg-subtle border border-base p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="relative flex w-2 h-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="text-xs font-medium text-primary">6 Agents Online</span>
            </div>
            <p className="text-[11px] text-tertiary">ChromaDB connected · 24 docs indexed</p>
          </div>
        </div>
      </aside>
    </>
  );
}
