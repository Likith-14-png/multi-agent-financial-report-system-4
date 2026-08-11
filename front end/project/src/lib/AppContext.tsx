import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { PageId } from '@/lib/types';

interface AppState {
  authed: boolean;
  user: { name: string; email: string } | null;
  login: (email: string) => void;
  logout: () => void;

  theme: 'light' | 'dark';
  toggleTheme: () => void;

  page: PageId;
  setPage: (p: PageId) => void;

  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;

  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(false);
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [page, setPage] = useState<PageId>('dashboard');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const login = useCallback((email: string) => {
    const name = email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    setUser({ name: name || 'Analyst', email });
    setAuthed(true);
    setPage('dashboard');
  }, []);

  const logout = useCallback(() => {
    setAuthed(false);
    setUser(null);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'light' ? 'dark' : 'light'));
  }, []);

  return (
    <AppContext.Provider
      value={{
        authed,
        user,
        login,
        logout,
        theme,
        toggleTheme,
        page,
        setPage,
        activeSessionId,
        setActiveSessionId,
        sidebarOpen,
        setSidebarOpen,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
