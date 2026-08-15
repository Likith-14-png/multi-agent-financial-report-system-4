import { AppProvider, useApp } from '@/lib/AppContext';
import { Sidebar } from '@/components/Sidebar';
import { TopBar } from '@/components/TopBar';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { WorkspacePage } from '@/pages/WorkspacePage';
import { ChatPage } from '@/pages/ChatPage';
import { ComparisonPage } from '@/pages/ComparisonPage';
import { InsightsPage } from '@/pages/InsightsPage';
import { RedFlagsPage } from '@/pages/RedFlagsPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { HistoryPage } from '@/pages/HistoryPage';
import { SettingsPage } from '@/pages/SettingsPage';

function AppContent() {
  const { authed, page } = useApp();

  if (!authed) return <LoginPage />;

  const pages: Record<string, React.ReactNode> = {
    dashboard: <DashboardPage />,
    workspace: <WorkspacePage />,
    chat: <ChatPage />,
    comparison: <ComparisonPage />,
    insights: <InsightsPage />,
    redflags: <RedFlagsPage />,
    reports: <ReportsPage />,
    history: <HistoryPage />,
    settings: <SettingsPage />,
  };

  return (
    <div className="flex bg-base min-h-screen">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar />
        <main className="flex-1 p-4 lg:p-6 max-w-[1600px] w-full mx-auto">
          {pages[page] ?? <DashboardPage />}
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;
