from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List


class ContextNotFoundError(LookupError):
    """Raised when an agent is called without its prerequisite analysis."""


@dataclass
class AnalysisContext:
    analysis_id: str
    document_id: str
    company_name: str = ""
    report_year: str = ""
    question: str = ""
    document_path: str = ""
    collection_name: str = "financial_research_v1"
    chroma_path: str = "enterprise_chroma_db"
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    document: Dict[str, Any] = field(default_factory=dict)
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    extraction: Dict[str, Any] = field(default_factory=dict)
    red_flags: Dict[str, Any] = field(default_factory=dict)
    research: Dict[str, Any] = field(default_factory=dict)
    comparison: Dict[str, Any] = field(default_factory=dict)
    report: Dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, Any]:
        payload = {
            "analysis_id": self.analysis_id,
            "document_id": self.document_id,
            "company_name": self.company_name,
            "report_year": self.report_year,
            "question": self.question,
            "document_path": self.document_path,
            "collection_name": self.collection_name,
            "chroma_path": self.chroma_path,
            "sources": self.sources,
            "metadata": self.metadata,
            "document": self.document,
            "chunks": self.chunks,
            "extraction": self.extraction,
            "red_flags": self.red_flags,
            "research": self.research,
            "comparison": self.comparison,
            "report": self.report,
        }
        return payload


def build_context(analysis_id: str, document_id: str, company_name: str, report_year: str, **kwargs: Any) -> AnalysisContext:
    return AnalysisContext(
        analysis_id=analysis_id,
        document_id=document_id,
        company_name=company_name,
        report_year=report_year,
        **kwargs,
    )


class AnalysisContextStore:
    """Thread-safe, replaceable storage boundary for in-process API workflows.

    The API owns one store instance.  Keeping this small repository separate
    from FastAPI means a database-backed implementation can replace it later
    without changing any agent or endpoint contracts.
    """

    def __init__(self) -> None:
        self._contexts: Dict[str, AnalysisContext] = {}
        self._lock = RLock()

    def create(self, context: AnalysisContext) -> AnalysisContext:
        with self._lock:
            self._contexts[context.analysis_id] = deepcopy(context)
            return deepcopy(context)

    def get(self, analysis_id: str) -> AnalysisContext | None:
        with self._lock:
            context = self._contexts.get(analysis_id)
            return deepcopy(context) if context else None

    def require(self, analysis_id: str) -> AnalysisContext:
        context = self.get(analysis_id)
        if context is None:
            raise ContextNotFoundError(
                "Analysis/document context not found. Run /analysis/document first."
            )
        return context

    def save(self, context: AnalysisContext) -> AnalysisContext:
        return self.create(context)
