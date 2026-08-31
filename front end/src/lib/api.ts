/**
 * FinSight AI — Centralized Typed API Client
 * Connects directly to verified FastAPI backend at http://localhost:8000
 */

import {
  HealthStatus,
  AnalysisUploadResponse,
  AnalysisStatusResponse,
  ExtractionResponse,
  ResearchResponse,
  ResearchQueryResponse,
  RedFlagsResponse,
  RedFlagsQueryResponse,
  ComparisonResponse,
  ReportResponse,
} from './types';

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string) || '';

/**
 * Custom API Error containing status code and structured detail
 */
export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: string;

  constructor(message: string, status: number, detail?: string, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorDetail = response.statusText;
    let errorCode = 'REQUEST_FAILED';
    try {
      const json = await response.json();
      if (typeof json.detail === 'string') {
        errorDetail = json.detail;
      } else if (typeof json.message === 'string') {
        errorDetail = json.message;
      } else if (json.error?.message) {
        errorDetail = json.error.message;
        errorCode = json.error.code || errorCode;
      }
    } catch {
      // Not JSON response
    }
    throw new ApiError(errorDetail || `Request failed with status ${response.status}`, response.status, errorDetail, errorCode);
  }
  return response.json() as Promise<T>;
}

export const api = {
  /**
   * 1. Health check
   */
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return handleResponse<HealthStatus>(res);
  },

  /**
   * 2. Upload Document A for analysis
   */
  async uploadAnalysis(
    file: File,
    companyName?: string,
    reportYear?: string,
    question?: string
  ): Promise<AnalysisUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (companyName?.trim()) {
      formData.append('company_name', companyName.trim());
    }
    if (reportYear?.trim()) {
      formData.append('report_year', reportYear.trim());
    }
    if (question?.trim()) {
      formData.append('question', question.trim());
    }

    const res = await fetch(`${API_BASE_URL}/analysis/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<AnalysisUploadResponse>(res);
  },

  /**
   * 3. Get Analysis Processing Status
   */
  async getAnalysisStatus(analysisId: string): Promise<AnalysisStatusResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/status`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return handleResponse<AnalysisStatusResponse>(res);
  },

  /**
   * 4. Retrieve Extracted Financial Metrics
   */
  async getExtraction(analysisId: string): Promise<ExtractionResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/extraction`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return handleResponse<ExtractionResponse>(res);
  },

  /**
   * 5. Retrieve Initial Grounded Research Synthesis
   */
  async getResearch(analysisId: string): Promise<ResearchResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/research`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return handleResponse<ResearchResponse>(res);
  },

  /**
   * 6. Ask Grounded Research Query
   */
  async queryResearch(analysisId: string, question: string): Promise<ResearchQueryResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/research/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ question: question.trim() }),
    });
    return handleResponse<ResearchQueryResponse>(res);
  },

  /**
   * 7. Retrieve Financial Risk Analysis & Red Flags
   */
  async getRedFlags(analysisId: string): Promise<RedFlagsResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/red-flags`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return handleResponse<RedFlagsResponse>(res);
  },

  /**
   * 8. Ask Grounded Red Flag / Risk Query
   */
  async queryRedFlags(analysisId: string, question: string): Promise<RedFlagsQueryResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/red-flags/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ question: question.trim() }),
    });
    return handleResponse<RedFlagsQueryResponse>(res);
  },

  /**
   * 9. Upload Document B for Cross-Company Comparison
   */
  async uploadComparison(
    analysisId: string,
    file: File,
    companyName?: string,
    reportYear?: string
  ): Promise<ComparisonResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (companyName?.trim()) {
      formData.append('company_name', companyName.trim());
    }
    if (reportYear?.trim()) {
      formData.append('report_year', reportYear.trim());
    }

    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/comparison/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<ComparisonResponse>(res);
  },

  /**
   * 10. Retrieve Cross-Company Comparison Results
   * Returns null on 404 (Peer not yet uploaded)
   */
  async getComparison(analysisId: string): Promise<ComparisonResponse | null> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/comparison`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    if (res.status === 404) {
      return null;
    }
    return handleResponse<ComparisonResponse>(res);
  },

  /**
   * 11. Retrieve Synthesized Executive Report JSON
   */
  async getReport(analysisId: string): Promise<ReportResponse> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/report`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    return handleResponse<ReportResponse>(res);
  },

  /**
   * 12. Download Executive Report PDF
   * Streams binary PDF directly to browser save dialog
   */
  async downloadReportPdf(
    analysisId: string,
    companyName?: string,
    reportYear?: string | number
  ): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/analysis/${encodeURIComponent(analysisId)}/report/download`, {
      method: 'GET',
    });

    if (!res.ok) {
      throw new ApiError('Failed to download PDF report', res.status);
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeCompany = (companyName || 'company').replace(/[^\w-]/g, '_');
    const safeYear = reportYear || 'report';
    link.download = `financial_report_${safeCompany}_${safeYear}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};
