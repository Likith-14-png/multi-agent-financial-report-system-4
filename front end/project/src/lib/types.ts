export type AgentStatus = 'waiting' | 'running' | 'completed';

export type AgentId =
  | 'document'
  | 'extraction'
  | 'redflag'
  | 'comparison'
  | 'research'
  | 'report';

export interface AgentInfo {
  id: AgentId;
  name: string;
  icon: string;
  description: string;
  responsibilities: string[];
  status: AgentStatus;
  progress: number;
}

export interface UploadedDoc {
  id: string;
  name: string;
  size: string;
  company: string;
  uploadedAt: string;
  status: 'queued' | 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'ready';
}

export interface PipelineStep {
  key: string;
  label: string;
  done: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: { label: string; source: string; page?: number }[];
}

export interface CompanyFinancials {
  ticker: string;
  name: string;
  revenue: number;
  netIncome: number;
  assets: number;
  liabilities: number;
  debt: number;
  operatingMargin: number;
  cashFlow: number;
  eps: number;
  revenueHistory: number[];
  profitHistory: number[];
  sector: string;
}

export interface RedFlag {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium';
  company: string;
  description: string;
  metric: string;
  value: string;
  trend: 'up' | 'down';
}

export interface ResearchSession {
  id: string;
  name: string;
  companies: string[];
  uploadDate: string;
  documents: number;
  status: 'completed' | 'in-progress' | 'queued';
}

export type PageId =
  | 'dashboard'
  | 'workspace'
  | 'chat'
  | 'comparison'
  | 'insights'
  | 'redflags'
  | 'reports'
  | 'history'
  | 'settings';
