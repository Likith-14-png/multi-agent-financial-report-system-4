import { useState } from 'react';
import { useApp } from '@/lib/AppContext';
import { Card, Badge, PageHeader } from '@/components/ui';
import { Icon } from '@/components/Icon';

const SECTIONS = [
  { id: 'profile', label: 'Profile', icon: 'User' },
  { id: 'agents', label: 'AI Agents', icon: 'BrainCircuit' },
  { id: 'notifications', label: 'Notifications', icon: 'Bell' },
  { id: 'security', label: 'Security', icon: 'ShieldCheck' },
];

export function SettingsPage() {
  const { user, theme, toggleTheme, logout } = useApp();
  const [active, setActive] = useState('profile');

  return (
    <div className="animate-fade-in">
      <PageHeader title="Settings" subtitle="Manage your account and platform preferences" />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar nav */}
        <Card className="p-3 h-fit lg:sticky lg:top-20">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setActive(s.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                active === s.id ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300' : 'text-secondary hover:bg-subtle'
              }`}
            >
              <Icon name={s.icon} size={18} className={active === s.id ? 'text-brand-600 dark:text-brand-400' : 'text-tertiary'} />
              {s.label}
            </button>
          ))}
        </Card>

        {/* Content */}
        <div className="lg:col-span-3">
          {active === 'profile' && (
            <Card className="p-6">
              <h3 className="text-base font-semibold text-primary mb-1">Profile Information</h3>
              <p className="text-xs text-secondary mb-5">Update your personal details and preferences.</p>

              <div className="flex items-center gap-4 mb-6 pb-6 border-b border-base">
                <div className="w-16 h-16 rounded-2xl gradient-brand flex items-center justify-center text-white text-2xl font-bold">
                  {user?.name?.charAt(0) ?? 'A'}
                </div>
                <div>
                  <p className="text-base font-semibold text-primary">{user?.name}</p>
                  <p className="text-sm text-secondary">{user?.email}</p>
                  <Badge variant="brand" className="mt-1">Research Analyst</Badge>
                </div>
                <button className="ml-auto px-3.5 py-2 rounded-xl border border-base text-sm text-secondary hover:bg-subtle transition-colors">
                  Change Photo
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-primary mb-1.5">Full Name</label>
                  <input type="text" defaultValue={user?.name} className="w-full px-3.5 py-2.5 rounded-xl border border-base bg-surface text-sm text-primary outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary mb-1.5">Email</label>
                  <input type="email" defaultValue={user?.email} className="w-full px-3.5 py-2.5 rounded-xl border border-base bg-surface text-sm text-primary outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary mb-1.5">Role</label>
                  <select className="w-full px-3.5 py-2.5 rounded-xl border border-base bg-surface text-sm text-primary outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10">
                    <option>Research Analyst</option>
                    <option>MBA Student</option>
                    <option>Portfolio Manager</option>
                    <option>Financial Advisor</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary mb-1.5">Organization</label>
                  <input type="text" defaultValue="Infosys Springboard" className="w-full px-3.5 py-2.5 rounded-xl border border-base bg-surface text-sm text-primary outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10" />
                </div>
              </div>

              <div className="flex items-center gap-2 mt-6">
                <button className="px-4 py-2.5 rounded-xl gradient-brand text-white text-sm font-medium shadow-card hover:shadow-elevated transition-all">
                  Save Changes
                </button>
                <button className="px-4 py-2.5 rounded-xl border border-base text-sm font-medium text-secondary hover:bg-subtle transition-colors">
                  Cancel
                </button>
              </div>
            </Card>
          )}

          {active === 'agents' && (
            <Card className="p-6">
              <h3 className="text-base font-semibold text-primary mb-1">AI Agent Configuration</h3>
              <p className="text-xs text-secondary mb-5">Configure how the six agents operate.</p>
              <div className="space-y-4">
                {[
                  { name: 'Document Agent', desc: 'Chunk size, embedding model, ChromaDB collection', icon: 'FileText' },
                  { name: 'Extraction Agent', desc: 'Financial metrics extraction templates', icon: 'TableProperties' },
                  { name: 'Red Flag Agent', desc: 'Risk thresholds and alert sensitivity', icon: 'ShieldAlert' },
                  { name: 'Comparison Agent', desc: 'Benchmark peer groups and metrics', icon: 'BarChart3' },
                  { name: 'Research Agent', desc: 'LLM model, temperature, max tokens', icon: 'BrainCircuit' },
                  { name: 'Report Agent', desc: 'Report templates and branding', icon: 'FileCheck2' },
                ].map((a, i) => (
                  <div key={i} className="flex items-center gap-3 p-4 rounded-xl border border-base hover:bg-subtle transition-colors">
                    <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-brand-500/10 flex items-center justify-center">
                      <Icon name={a.icon} size={20} className="text-brand-600 dark:text-brand-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-primary">{a.name}</p>
                      <p className="text-xs text-secondary">{a.desc}</p>
                    </div>
                    <button className="px-3 py-1.5 rounded-lg border border-base text-xs font-medium text-secondary hover:bg-surface transition-colors">
                      Configure
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {active === 'notifications' && (
            <Card className="p-6">
              <h3 className="text-base font-semibold text-primary mb-1">Notification Preferences</h3>
              <p className="text-xs text-secondary mb-5">Choose what alerts you receive.</p>
              <div className="space-y-1">
                {[
                  { label: 'Agent completion alerts', desc: 'Get notified when an agent finishes processing', on: true },
                  { label: 'Red flag warnings', desc: 'Immediate alerts for critical risk detections', on: true },
                  { label: 'Report ready notifications', desc: 'Be notified when reports are generated', on: true },
                  { label: 'Weekly digest', desc: 'Summary of your research activity every Monday', on: false },
                  { label: 'Product updates', desc: 'New features and platform announcements', on: false },
                ].map((n, i) => (
                  <ToggleRow key={i} label={n.label} desc={n.desc} defaultOn={n.on} />
                ))}
              </div>
            </Card>
          )}

          {active === 'security' && (
            <Card className="p-6">
              <h3 className="text-base font-semibold text-primary mb-1">Security & Appearance</h3>
              <p className="text-xs text-secondary mb-5">Manage authentication and display settings.</p>
              <div className="space-y-1">
                <ToggleRow label="Two-factor authentication" desc="Add an extra layer of security to your account" defaultOn={false} />
                <ToggleRow
                  label="Dark mode"
                  desc="Switch between light and dark interface themes"
                  defaultOn={theme === 'dark'}
                  onToggle={toggleTheme}
                />
                <ToggleRow label="Session timeout" desc="Automatically sign out after 30 minutes of inactivity" defaultOn={true} />
              </div>
              <div className="mt-6 pt-6 border-t border-base">
                <button onClick={logout} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-red-200 dark:border-red-500/20 text-sm font-medium text-danger-600 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors">
                  <Icon name="LogOut" size={16} /> Sign Out
                </button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function ToggleRow({ label, desc, defaultOn, onToggle }: { label: string; desc: string; defaultOn: boolean; onToggle?: () => void }) {
  const [on, setOn] = useState(defaultOn);
  const toggle = () => {
    setOn(!on);
    onToggle?.();
  };
  return (
    <div className="flex items-center justify-between py-3 border-b border-base last:border-0">
      <div>
        <p className="text-sm font-medium text-primary">{label}</p>
        <p className="text-xs text-secondary mt-0.5">{desc}</p>
      </div>
      <button
        onClick={toggle}
        className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${on ? 'bg-brand-500' : 'bg-slate-300 dark:bg-slate-600'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${on ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  );
}
