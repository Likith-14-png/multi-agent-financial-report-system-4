from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AnalysisSession:
    analysis_id: str
    document_id: str
    company_name: Optional[str] = None
    report_year: Optional[int | str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    status: str = "processing"
    current_agent: Optional[str] = None
    progress: int = 0
    extraction_result: Dict[str, Any] = field(default_factory=dict)
    research_result: Dict[str, Any] = field(default_factory=dict)
    red_flags_result: Dict[str, Any] = field(default_factory=dict)
    comparison_result: Optional[Dict[str, Any]] = None
    report_result: Dict[str, Any] = field(default_factory=dict)
    pdf_path: Optional[str] = None
    comparison_document_id: Optional[str] = None
    comparison_id: Optional[str] = None
    comparison_company_name: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "document_id": self.document_id,
            "company_name": self.company_name,
            "report_year": self.report_year,
            "file_name": self.file_name,
            "status": self.status,
            "current_agent": self.current_agent,
            "progress": self.progress,
            "extraction_result": self.extraction_result,
            "research_result": self.research_result,
            "red_flags_result": self.red_flags_result,
            "comparison_result": self.comparison_result,
            "report_result": self.report_result,
            "pdf_path": self.pdf_path,
            "comparison_document_id": self.comparison_document_id,
            "comparison_id": self.comparison_id,
            "comparison_company_name": self.comparison_company_name,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SessionStore:
    """Thread-safe in-memory session manager for Multi-Agent Financial Research System."""

    def __init__(self) -> None:
        self._sessions: Dict[str, AnalysisSession] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        analysis_id: str,
        document_id: str,
        company_name: Optional[str] = None,
        report_year: Optional[int | str] = None,
        file_path: Optional[str] = None,
        file_name: Optional[str] = None,
        status: str = "processing",
        current_agent: Optional[str] = "document",
        progress: int = 10,
        **kwargs: Any,
    ) -> AnalysisSession:
        with self._lock:
            session = AnalysisSession(
                analysis_id=analysis_id,
                document_id=document_id,
                company_name=company_name,
                report_year=report_year,
                file_path=file_path,
                file_name=file_name,
                status=status,
                current_agent=current_agent,
                progress=progress,
                **kwargs,
            )
            self._sessions[analysis_id] = session
            return session

    def get_session(self, analysis_id: str) -> Optional[AnalysisSession]:
        with self._lock:
            return self._sessions.get(analysis_id)

    def update_session(self, analysis_id: str, **kwargs: Any) -> Optional[AnalysisSession]:
        with self._lock:
            session = self._sessions.get(analysis_id)
            if session:
                session.update(**kwargs)
            return session

    def delete_session(self, analysis_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(analysis_id, None) is not None

    def list_sessions(self) -> List[AnalysisSession]:
        with self._lock:
            return list(self._sessions.values())

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


# Global default instance
session_store = SessionStore()
