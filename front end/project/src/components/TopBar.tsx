import { useState } from 'react';
import { useApp } from '@/lib/AppContext';
import { Icon } from '@/components/Icon';

export function TopBar() {
  const { user, logout, theme, toggleTheme, setSidebarOpen, setPage } = useApp();
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 h-16 bg-surface/80 backdrop-blur-xl border-b border-base flex items-center gap-3 px-4 lg:px-6">
      <button onClick={() => setSidebarOpen(true)} className="lg:hidden p-2 rounded-lg hover:bg-subtle text-secondary">
        <Icon name="Menu" size={20} />
      </button>

      {/* Search */}
      <div className="relative flex-1 max-w-md">
        <Icon name="Search" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary" />
        <input
          type="text"
          placeholder="Search companies, filings, sessions…"
          className="w-full pl-10 pr-4 py-2 rounded-xl border border-base bg-subtle text-sm text-primary outline-none transition-all focus:bg-surface focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10 placeholder:text-tertiary"
        />
        <kbd className="hidden sm:flex absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-tertiary border border-base rounded px-1.5 py-0.5 bg-surface">⌘K</kbd>
      </div>

      <div className="flex items-center gap-1 ml-auto">
        {/* Dark mode toggle */}
        <button
          onClick={toggleTheme}
          className="p-2.5 rounded-xl hover:bg-subtle text-secondary transition-colors"
          title="Toggle theme"
        >
          <Icon name={theme === 'light' ? 'Moon' : 'Sun'} size={19} />
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }}
            className="p-2.5 rounded-xl hover:bg-subtle text-secondary transition-colors relative"
          >
            <Icon name="Bell" size={19} />
            <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-danger-500 border-2 border-surface" />
          </button>
          {notifOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setNotifOpen(false)} />
              <div className="absolute right-0 mt-2 w-80 bg-surface border border-base rounded-2xl shadow-elevated z-20 overflow-hidden animate-fade-in">
                <div className="px-4 py-3 border-b border-base flex items-center justify-between">
                  <span className="text-sm font-semibold text-primary">Notifications</span>
                  <button className="text-xs text-brand-600 hover:text-brand-700 font-medium">Mark all read</button>
                </div>
                <div className="max-h-80 overflow-y-auto scrollbar-thin">
                  {[
                    { icon: 'CheckCircle2', color: 'text-emerald-500', title: 'Document Agent completed', desc: 'Microsoft 10-K indexed in ChromaDB', time: '2m ago' },
                    { icon: 'ShieldAlert', color: 'text-amber-500', title: 'Red Flag detected', desc: 'Amazon debt-to-equity above threshold', time: '8m ago' },
                    { icon: 'FileCheck2', color: 'text-brand-500', title: 'Report ready', desc: 'Big Tech Q4 Comparison report generated', time: '1h ago' },
                  ].map((n, i) => (
                    <div key={i} className="px-4 py-3 hover:bg-subtle border-b border-base last:border-0 cursor-pointer">
                      <div className="flex gap-3">
                        <Icon name={n.icon} size={18} className={n.color + ' shrink-0 mt-0.5'} />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-primary">{n.title}</p>
                          <p className="text-xs text-secondary truncate">{n.desc}</p>
                          <p className="text-[11px] text-tertiary mt-0.5">{n.time}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Profile */}
        <div className="relative ml-1">
          <button
            onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}
            className="flex items-center gap-2 p-1 pr-2 rounded-xl hover:bg-subtle transition-colors"
          >
            <div className="w-8 h-8 rounded-lg gradient-brand flex items-center justify-center text-white text-sm font-semibold shrink-0">
              {user?.name?.charAt(0) ?? 'A'}
            </div>
            <div className="hidden sm:block text-left">
              <p className="text-sm font-medium text-primary leading-tight">{user?.name ?? 'Analyst'}</p>
              <p className="text-[11px] text-tertiary leading-tight">Research Analyst</p>
            </div>
            <Icon name="ChevronDown" size={16} className="hidden sm:block text-tertiary" />
          </button>
          {profileOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
              <div className="absolute right-0 mt-2 w-56 bg-surface border border-base rounded-2xl shadow-elevated z-20 overflow-hidden animate-fade-in">
                <div className="px-4 py-3 border-b border-base">
                  <p className="text-sm font-medium text-primary">{user?.name}</p>
                  <p className="text-xs text-tertiary truncate">{user?.email}</p>
                </div>
                <div className="py-1">
                  <button onClick={() => { setProfileOpen(false); setPage('settings'); }} className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-secondary hover:bg-subtle hover:text-primary">
                    <Icon name="Settings" size={16} /> Settings
                  </button>
                  <button className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-secondary hover:bg-subtle hover:text-primary">
                    <Icon name="User" size={16} /> Profile
                  </button>
                  <div className="border-t border-base my-1" />
                  <button onClick={logout} className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-danger-600 hover:bg-red-50 dark:hover:bg-red-500/10">
                    <Icon name="LogOut" size={16} /> Sign out
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
