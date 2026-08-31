import React from 'react';
import { AppProvider, useApp } from './lib/AppContext';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { CitationDrawer } from './components/CitationDrawer';

// Pages
import { WorkspacePage } from './pages/WorkspacePage';
import { OverviewPage } from './pages/OverviewPage';
import { FinancialsPage } from './pages/FinancialsPage';
import { ResearchPage } from './pages/ResearchPage';
import { RiskPage } from './pages/RiskPage';
import { ComparisonPage } from './pages/ComparisonPage';
import { ReportPage } from './pages/ReportPage';
import { HistoryPage } from './pages/HistoryPage';
import { SettingsPage } from './pages/SettingsPage';

function AppContent() {
  const { activeView } = useApp();

  const renderActivePage = () => {
    switch (activeView) {
      case 'workspace':
        return <WorkspacePage />;
      case 'overview':
        return <OverviewPage />;
      case 'financials':
        return <FinancialsPage />;
      case 'research':
        return <ResearchPage />;
      case 'risk':
        return <RiskPage />;
      case 'comparison':
        return <ComparisonPage />;
      case 'report':
        return <ReportPage />;
      case 'history':
        return <HistoryPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <WorkspacePage />;
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500/20 selection:text-cyan-200">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          {renderActivePage()}
        </main>
      </div>

      {/* Global Citation & Evidence Drawer */}
      <CitationDrawer />
    </div>
  );
}

export function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
