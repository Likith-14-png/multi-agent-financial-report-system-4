/**
 * FinSight AI — TypeScript Types & API Contract Interfaces
 * Strictly aligned with FastAPI backend models
 */

export type ActiveView =
  | 'workspace'
  | 'overview'
  | 'financials'
  | 'research'
  | 'risk'
  | 'comparison'
  | 'report'
  | 'history'
  | 'settings';

export type RiskSeverity = 'Critical' | 'High' | 'Medium' | 'Low';

export interface HealthStatus {
  status: string;
  service: string;
}

export interface DocumentChunk {
  chunk_id: string;
  chunk_index?: number | null;
  page_number?: string | number | null;
  page_start?: number | null;
  page_end?: number | null;
  section_title?: string | null;
  section_type?: string | null;
  text?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AnalysisUploadResponse {
  status: string;
  message: string;
  analysis_id: string;
  document_id: string;
  company_name?: string | null;
  report_year?: number | string | null;
  document?: string | null;
  collection?: string | null;
  total_chunks: number;
  chunks?: DocumentChunk[];
  quality_report?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
}

export interface AnalysisStatusResponse {
  analysis_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | string;
  current_agent?: string | null;
  progress: number;
}

export interface ProvenanceInfo {
  source_file?: string | null;
  page?: string | number | null;
  chunk_id?: string | null;
  section?: string | null;
}

export interface MetricRecord {
  metric: string;
  value: string | number | null;
  currency?: string | null;
  unit?: string | null;
  period?: string | number | null;
  evidence?: string | null;
  page?: string | number | null;
  source?: string | null;
  chunk_id?: string | null;
  provenance?: ProvenanceInfo | null;
}

export interface YearlyMetricPoint {
  year?: string | number | null;
  period?: string | number | null;
  value?: string | number | null;
  currency?: string | null;
  unit?: string | null;
  source_file?: string | null;
  page?: string | number | null;
  section?: string | null;
  chunk_id?: string | null;
  evidence?: string | null;
  provenance?: ProvenanceInfo | null;
}

export interface ObservationItem {
  metric?: string | null;
  metric_name?: string | null;
  canonical_label?: string | null;
  value?: string | number | null;
  raw_value?: string | number | null;
  currency?: string | null;
  unit?: string | null;
  period?: string | number | null;
  year?: string | number | null;
  report_year?: string | number | null;
  source_file?: string | null;
  page?: string | number | null;
  section?: string | null;
  chunk_id?: string | null;
  evidence?: string | null;
  provenance?: ProvenanceInfo | null;
}

export interface ExtractionResponse {
  analysis_id?: string | null;
  document_id?: string | null;
  company_name?: string | null;
  report_year?: string | number | null;
  revenue?: string | number | null;
  gross_profit?: string | number | null;
  operating_income?: string | number | null;
  pretax_income?: string | number | null;
  net_income?: string | number | null;
  total_assets?: string | number | null;
  total_liabilities?: string | number | null;
  total_equity?: string | number | null;
  cash_flow?: string | number | null;
  operating_cash_flow?: string | number | null;
  free_cash_flow?: string | number | null;
  rd_expense?: string | number | null;
  eps?: string | number | null;
  basic_eps?: string | number | null;
  diluted_eps?: string | number | null;
  trend_eps?: string | number | null;
  metrics?: MetricRecord[];
  yearly_metrics?: Record<string, YearlyMetricPoint[]> | null;
  observations?: ObservationItem[] | null;
  detailed_metrics?: ObservationItem[] | null;
  income_statement?: Record<string, unknown> | null;
  balance_sheet?: Record<string, unknown> | null;
  cash_flow_statement?: Record<string, unknown> | null;
  segment_metrics?: Record<string, unknown> | null;
  source?: string | null;
  source_file?: string | null;
  chunk_id?: string | null;
}

export interface CitationSource {
  snippet?: string | null;
  source_file?: string | null;
  page?: string | number | null;
  chunk_id?: string | null;
  score?: number | null;
  section?: string | null;
  relevance?: number | null;
}

export interface ResearchResponse {
  analysis_id?: string | null;
  status?: string | null;
  question?: string | null;
  answer?: string | null;
  final_answer?: string | null;
  summary?: string | null;
  sources: CitationSource[];
  evidence?: Array<Record<string, unknown>>;
  steps?: Array<Record<string, unknown>> | null;
  citations?: CitationSource[] | null;
  findings?: Array<string | Record<string, unknown>> | null;
  source_chunks?: string[] | null;
  model_used?: string | null;
}

export interface ResearchQueryResponse {
  analysis_id: string;
  question: string;
  answer: string;
  status?: string | null;
  summary?: string | null;
  sources: CitationSource[];
  evidence?: Array<Record<string, unknown>>;
  steps?: Array<Record<string, unknown>> | null;
  citations?: CitationSource[] | null;
  findings?: Array<string | Record<string, unknown>> | null;
  source_chunks?: string[] | null;
  model_used?: string | null;
}

export interface RedFlagItem {
  id?: string | number;
  category?: string | null;
  title?: string | null;
  description?: string | null;
  reason?: string | null;
  evidence?: string | null;
  page?: string | number | null;
  recommendation?: string | null;
  confidence?: number | string | null;
  severity?: RiskSeverity | string | null;
  risk_level?: RiskSeverity | string | null;
  impact?: string | null;
  metric?: string | null;
  source_chunk?: string | null;
}

export interface RedFlagsResponse {
  analysis_id?: string | null;
  overall_risk: RiskSeverity | string;
  total_flags: number;
  flags: RedFlagItem[];
  model_used?: string | null;
  execution_time?: number | null;
  metadata?: Record<string, unknown> | null;
}

export interface RedFlagsQueryResponse {
  analysis_id: string;
  question: string;
  answer: string;
  sources: CitationSource[];
}

export interface ComparisonRecord {
  metric: string;
  company_a_value?: string | number | null;
  company_b_value?: string | number | null;
  company_a?: string | number | Record<string, unknown> | null;
  company_b?: string | number | Record<string, unknown> | null;
  difference?: string | number | null;
  difference_pct?: string | number | null;
  diff_percent?: string | number | null;
  percentage_difference?: string | number | null;
  direction?: 'higher' | 'lower' | 'equal' | 'favorable' | 'unfavorable' | string | null;
  interpretation?: string | null;
  category?: string | null;
  unit?: string | null;
}

export interface ComparisonResponse {
  analysis_id?: string | null;
  comparison_id?: string | null;
  status?: string | null;
  companies: string[];
  metrics?: Array<Record<string, unknown>>;
  records: ComparisonRecord[];
  summary?: Record<string, unknown> | string | null;
  metadata?: Record<string, unknown> | null;
  comparison_type?: string | null;
}

export interface ReportResponse {
  analysis_id?: string | null;
  document_id?: string | null;
  company_name?: string | null;
  report_year?: string | number | null;
  executive_summary?: string | null;
  financial_metrics?: Array<Record<string, unknown>> | null;
  research_findings?: Array<Record<string, unknown>> | null;
  risk_assessment?: Record<string, unknown> | null;
  comparison?: Record<string, unknown> | null;
  evidence?: Array<Record<string, unknown>> | null;
  recommendations?: string[] | null;
  report_status?: 'complete' | 'partial' | 'failed' | string | null;
  extraction?: Record<string, unknown> | null;
  research?: Record<string, unknown> | null;
  red_flags?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
}

export interface RecentAnalysisItem {
  analysis_id: string;
  document_id?: string;
  company_name?: string;
  report_year?: string | number;
  document_name?: string;
  created_at: string;
  total_chunks?: number;
  overall_risk?: string;
}

export interface ResearchChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  sources?: CitationSource[];
  modelUsed?: string;
  isStreaming?: boolean;
}
