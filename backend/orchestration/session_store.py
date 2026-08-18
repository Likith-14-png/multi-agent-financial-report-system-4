from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class AnalysisSession:
    analysis_id: str
    document_id: str
    document_ids: list[str] = field(default_factory=list)
    status: str = "uploaded"
    current_agent: str | None = None
    company_name: str | None = None
    report_year: int | str | None = None
    extraction: dict[str, Any] = field(default_factory=dict)
    research: dict[str, Any] = field(default_factory=dict)
    red_flags: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)
    comparison_documents: list[dict[str, Any]] = field(default_factory=list)
    report_pdf_path: str | None = None
    error: str | None = None


class AnalysisSessionStore:
    """Small thread-safe in-memory store for API analysis sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, AnalysisSession] = {}
        self._lock = RLock()

    def create_session(
        self,
        analysis_id: str,
        document_id: str,
        *,
        company_name: str | None = None,
        report_year: int | str | None = None,
    ) -> AnalysisSession:
        with self._lock:
            if analysis_id in self._sessions:
                raise ValueError(f"Analysis session already exists: {analysis_id}")
            session = AnalysisSession(
                analysis_id=analysis_id,
                document_id=document_id,
                document_ids=[document_id],
                company_name=company_name,
                report_year=report_year,
            )
            self._sessions[analysis_id] = session
            return deepcopy(session)

    def get_session(self, analysis_id: str) -> AnalysisSession | None:
        with self._lock:
            session = self._sessions.get(analysis_id)
            return deepcopy(session) if session is not None else None

    def update_session(self, analysis_id: str, **updates: Any) -> AnalysisSession:
        with self._lock:
            session = self._sessions.get(analysis_id)
            if session is None:
                raise KeyError(analysis_id)
            for key, value in updates.items():
                if not hasattr(session, key):
                    raise ValueError(f"Unknown session field: {key}")
                setattr(session, key, deepcopy(value))
            return deepcopy(session)


session_store = AnalysisSessionStore()


def create_session(*args: Any, **kwargs: Any) -> AnalysisSession:
    return session_store.create_session(*args, **kwargs)


def get_session(analysis_id: str) -> AnalysisSession | None:
    return session_store.get_session(analysis_id)


def update_session(analysis_id: str, **updates: Any) -> AnalysisSession:
    return session_store.update_session(analysis_id, **updates)
