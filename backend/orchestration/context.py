from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
