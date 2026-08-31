import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ActiveView, CitationSource, RecentAnalysisItem } from './types';
import { api } from './api';

interface AppContextType {
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
  activeSessionId: string | null;
  activeCompany: string | null;
  activeYear: string | number | null;
  activeDocumentName: string | null;
  activeTotalChunks: number | null;
  setActiveSession: (params: {
    analysisId: string;
    companyName?: string | null;
    reportYear?: string | number | null;
    documentName?: string | null;
    totalChunks?: number | null;
    overallRisk?: string;
  }) => void;
  clearActiveSession: () => void;
  recentAnalyses: RecentAnalysisItem[];
  removeRecentAnalysis: (analysisId: string) => void;
  clearRecentAnalyses: () => void;
  theme: 'dark' | 'light';
  setTheme: (theme: 'dark' | 'light') => void;
  toggleTheme: () => void;
  isBackendHealthy: boolean | null;
  checkBackendHealth: () => Promise<boolean>;
  isEvidenceDrawerOpen: boolean;
  selectedCitation: CitationSource | null;
  openEvidenceDrawer: (citation: CitationSource) => void;
  closeEvidenceDrawer: () => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
}

const STORAGE_KEY_SESSION = 'finsight_active_session';
const STORAGE_KEY_RECENTS = 'finsight_recent_analyses';
const STORAGE_KEY_THEME = 'finsight_theme';

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [activeView, setActiveView] = useState<ActiveView>('workspace');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SESSION);
      return saved ? JSON.parse(saved).analysisId : null;
    } catch {
      return null;
    }
  });
  const [activeCompany, setActiveCompany] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SESSION);
      return saved ? JSON.parse(saved).companyName : null;
    } catch {
      return null;
    }
  });
  const [activeYear, setActiveYear] = useState<string | number | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SESSION);
      return saved ? JSON.parse(saved).reportYear : null;
    } catch {
      return null;
    }
  });
  const [activeDocumentName, setActiveDocumentName] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SESSION);
      return saved ? JSON.parse(saved).documentName : null;
    } catch {
      return null;
    }
  });
  const [activeTotalChunks, setActiveTotalChunks] = useState<number | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SESSION);
      return saved ? JSON.parse(saved).totalChunks : null;
    } catch {
      return null;
    }
  });

  const [recentAnalyses, setRecentAnalyses] = useState<RecentAnalysisItem[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_RECENTS);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [theme, setThemeState] = useState<'dark' | 'light'>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_THEME);
      return saved === 'light' ? 'light' : 'dark';
    } catch {
      return 'dark';
    }
  });

  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<CitationSource | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Sync theme class to html element
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.remove('dark');
      root.classList.add('light');
    }
    localStorage.setItem(STORAGE_KEY_THEME, theme);
  }, [theme]);

  // Check backend health on mount and periodically
  const checkBackendHealth = async (): Promise<boolean> => {
    try {
      const res = await api.getHealth();
      const healthy = res.status === 'ok' || res.status === 'healthy';
      setIsBackendHealthy(healthy);
      return healthy;
    } catch {
      setIsBackendHealthy(false);
      return false;
    }
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const setTheme = (newTheme: 'dark' | 'light') => {
    setThemeState(newTheme);
  };

  const toggleTheme = () => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const setActiveSession = ({
    analysisId,
    companyName = null,
    reportYear = null,
    documentName = null,
    totalChunks = null,
    overallRisk,
  }: {
    analysisId: string;
    companyName?: string | null;
    reportYear?: string | number | null;
    documentName?: string | null;
    totalChunks?: number | null;
    overallRisk?: string;
  }) => {
    setActiveSessionId(analysisId);
    setActiveCompany(companyName || 'Analyzed Company');
    setActiveYear(reportYear || '2025');
    setActiveDocumentName(documentName);
    setActiveTotalChunks(totalChunks);

    const sessionData = {
      analysisId,
      companyName: companyName || 'Analyzed Company',
      reportYear: reportYear || '2025',
      documentName,
      totalChunks,
    };
    localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(sessionData));

    // Update Recents
    setRecentAnalyses((prev) => {
      const filtered = prev.filter((item) => item.analysis_id !== analysisId);
      const updated: RecentAnalysisItem[] = [
        {
          analysis_id: analysisId,
          company_name: companyName || 'Analyzed Company',
          report_year: reportYear || '2025',
          document_name: documentName || undefined,
          created_at: new Date().toISOString(),
          total_chunks: totalChunks || undefined,
          overall_risk: overallRisk,
        },
        ...filtered,
      ].slice(0, 20); // Keep last 20
      localStorage.setItem(STORAGE_KEY_RECENTS, JSON.stringify(updated));
      return updated;
    });
  };

  const clearActiveSession = () => {
    setActiveSessionId(null);
    setActiveCompany(null);
    setActiveYear(null);
    setActiveDocumentName(null);
    setActiveTotalChunks(null);
    localStorage.removeItem(STORAGE_KEY_SESSION);
  };

  const removeRecentAnalysis = (analysisId: string) => {
    setRecentAnalyses((prev) => {
      const updated = prev.filter((item) => item.analysis_id !== analysisId);
      localStorage.setItem(STORAGE_KEY_RECENTS, JSON.stringify(updated));
      return updated;
    });
    if (activeSessionId === analysisId) {
      clearActiveSession();
      setActiveView('workspace');
    }
  };

  const clearRecentAnalyses = () => {
    setRecentAnalyses([]);
    localStorage.removeItem(STORAGE_KEY_RECENTS);
  };

  const openEvidenceDrawer = (citation: CitationSource) => {
    setSelectedCitation(citation);
    setIsEvidenceDrawerOpen(true);
  };

  const closeEvidenceDrawer = () => {
    setIsEvidenceDrawerOpen(false);
    setSelectedCitation(null);
  };

  return (
    <AppContext.Provider
      value={{
        activeView,
        setActiveView,
        activeSessionId,
        activeCompany,
        activeYear,
        activeDocumentName,
        activeTotalChunks,
        setActiveSession,
        clearActiveSession,
        recentAnalyses,
        removeRecentAnalysis,
        clearRecentAnalyses,
        theme,
        setTheme,
        toggleTheme,
        isBackendHealthy,
        checkBackendHealth,
        isEvidenceDrawerOpen,
        selectedCitation,
        openEvidenceDrawer,
        closeEvidenceDrawer,
        mobileMenuOpen,
        setMobileMenuOpen,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
