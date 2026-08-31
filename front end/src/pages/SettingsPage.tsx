import React, { useState } from 'react';
import {
  Settings,
  Sun,
  Moon,
  RefreshCw,
  Trash2,
  CheckCircle2,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

export function SettingsPage() {
  const {
    theme,
    setTheme,
    isBackendHealthy,
    checkBackendHealth,
    clearActiveSession,
    clearRecentAnalyses,
  } = useApp();

  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [clearedMessage, setClearedMessage] = useState(false);

  const handleHealthCheck = async () => {
    setIsCheckingHealth(true);
    await checkBackendHealth();
    setIsCheckingHealth(false);
  };

  const handleClearCache = () => {
    clearActiveSession();
    clearRecentAnalyses();
    setClearedMessage(true);
    setTimeout(() => setClearedMessage(false), 3000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-xs font-semibold text-cyan-300 mb-2">
          <Settings className="w-3.5 h-3.5" />
          <span>Workstation Configuration</span>
        </div>
        <h1 className="text-2xl font-extrabold text-white">Settings & Environment</h1>
        <p className="text-xs text-slate-400 mt-1">
          Manage interface theme, backend API connection, and local data persistence.
        </p>
      </div>

      {/* Theme Preference */}
      <Card className="border-slate-800 bg-slate-900/90 p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-100">Interface Appearance</h3>
            <p className="text-xs text-slate-400">Choose between dark analyst workstation and light mode</p>
          </div>
          <Badge variant="outline" size="sm">UI Theme</Badge>
        </div>

        <div className="grid grid-cols-2 gap-4 max-w-sm">
          <button
            onClick={() => setTheme('dark')}
            className={`p-4 rounded-xl border flex items-center gap-3 transition-all cursor-pointer ${
              theme === 'dark'
                ? 'border-cyan-500 bg-cyan-950/30 text-white font-semibold'
                : 'border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700'
            }`}
          >
            <Moon className="w-5 h-5 text-cyan-400" />
            <div className="text-left text-xs">
              <span className="block font-bold">Dark Slate</span>
              <span className="text-[10px] text-slate-400">Analyst Default</span>
            </div>
          </button>

          <button
            onClick={() => setTheme('light')}
            className={`p-4 rounded-xl border flex items-center gap-3 transition-all cursor-pointer ${
              theme === 'light'
                ? 'border-cyan-500 bg-cyan-950/30 text-white font-semibold'
                : 'border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700'
            }`}
          >
            <Sun className="w-5 h-5 text-amber-400" />
            <div className="text-left text-xs">
              <span className="block font-bold">Clean Light</span>
              <span className="text-[10px] text-slate-400">High Contrast</span>
            </div>
          </button>
        </div>
      </Card>

      {/* Backend API Service Status */}
      <Card className="border-slate-800 bg-slate-900/90 p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-100">FastAPI Backend Service</h3>
            <p className="text-xs text-slate-400">Connection state to Python orchestrator & ChromaDB</p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={handleHealthCheck}
            isLoading={isCheckingHealth}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Ping Health
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-400 uppercase tracking-wider text-[10px] font-bold">API Base Endpoint</span>
            <p className="font-mono text-cyan-300 text-sm">http://localhost:8000</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-400 uppercase tracking-wider text-[10px] font-bold">Health Status</span>
            <div className="flex items-center gap-2 pt-0.5">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isBackendHealthy === true
                    ? 'bg-emerald-500'
                    : isBackendHealthy === false
                    ? 'bg-rose-500'
                    : 'bg-amber-500'
                }`}
              />
              <span className="font-bold text-slate-100 text-sm">
                {isBackendHealthy === true
                  ? 'Healthy & Connected'
                  : isBackendHealthy === false
                  ? 'Offline / Unreachable'
                  : 'Checking Service...'}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Local Storage & Cache Management */}
      <Card className="border-slate-800 bg-slate-900/90 p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-100">Local Workstation Cache</h3>
            <p className="text-xs text-slate-400">Clear cached sessions and local history from browser storage</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-400 max-w-md">
            Resetting the local cache removes stored session IDs from your browser. Ingested ChromaDB vector collections on the backend remain intact.
          </p>

          <Button
            size="sm"
            variant="danger"
            onClick={handleClearCache}
            leftIcon={<Trash2 className="w-3.5 h-3.5" />}
          >
            Reset Local Storage
          </Button>
        </div>

        {clearedMessage && (
          <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Local session cache successfully cleared.</span>
          </div>
        )}
      </Card>
    </div>
  );
}
