from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DOC_AGENT_PATH = ROOT / "document-agent-text-chunking" / "scripts"
EXTRACTION_AGENT_PATH = ROOT / "extraction-agent"
RED_FLAG_PATH = ROOT / "red_flag_agent"
REPORT_AGENT_PATH = ROOT / "report-agent"
for path in (DOC_AGENT_PATH, EXTRACTION_AGENT_PATH, RED_FLAG_PATH, REPORT_AGENT_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from document_agent import DocumentAgent, DocumentAgentConfig
from extraction_agent import extract_report_metrics
from research_agent import ResearchAgent
from compare import compare_company_metrics, compare_report_metrics
from app.agents.crew import RedFlagCrew
from app.services.gemini_service import GeminiService
from report_agent import ReportAgent


class _AnalysisScopedCollection:
    """Adapter that adds an analysis_id filter without changing ResearchAgent."""

    def __init__(self, collection: Any, analysis_id: str) -> None:
        self._collection = collection
        self._analysis_id = analysis_id

    def _where(self, where: Optional[dict[str, Any]]) -> dict[str, Any]:
        if not where:
            return {"analysis_id": self._analysis_id}
        return {"$and": [{"analysis_id": self._analysis_id}, where]}

    def query(self, *args: Any, where: Optional[dict[str, Any]] = None, **kwargs: Any) -> Any:
        return self._collection.query(*args, where=self._where(where), **kwargs)

    def get(self, *args: Any, where: Optional[dict[str, Any]] = None, **kwargs: Any) -> Any:
        return self._collection.get(*args, where=self._where(where), **kwargs)


class AnalysisWorkflow:
    """Thin orchestration layer around the existing six agents."""

    def __init__(self, chroma_path: str | None = None, collection_name: str = "financial_research_v1") -> None:
        self.chroma_path = chroma_path or str(ROOT / "enterprise_chroma_db")
        self.collection_name = collection_name
        self.document_agent = DocumentAgent(
            DocumentAgentConfig(
                db_path=self.chroma_path,
                collection_name=self.collection_name,
                chunk_size=800,
                chunk_overlap=100,
                overwrite=True,
            )
        )

    @staticmethod
    def _get_current_document_records(
        collection: Any,
        company_name: str | None,
        document_id: str,
        analysis_id: str | None = None,
    ) -> List[tuple[str, Dict[str, Any]]]:
        if collection is None:
            return []
        filters: List[dict[str, Any]] = []
        if analysis_id and company_name:
            filters.append({"$and": [{"analysis_id": analysis_id}, {"company_name": company_name}, {"document_id": document_id}]})
        if company_name:
            filters.append({"$and": [{"company_name": company_name}, {"document_id": document_id}]})
        if analysis_id:
            filters.append({"$and": [{"analysis_id": analysis_id}, {"document_id": document_id}]})
        filters.append({"document_id": document_id})
        candidates: List[tuple[str, Dict[str, Any]]] = []
        for where in filters:
            try:
                results = collection.get(where=where, include=["documents", "metadatas"])
            except Exception:
                continue
            rows = []
            for doc, meta in zip(results.get("documents") or [], results.get("metadatas") or []):
                if not isinstance(doc, str) or not isinstance(meta, dict):
                    continue
                if str(meta.get("document_id") or "") != str(document_id):
                    continue
                if analysis_id and str(meta.get("analysis_id") or "") != str(analysis_id):
                    continue
                if company_name and str(meta.get("company_name") or "") != str(company_name):
                    continue
                rows.append((doc, meta))
            if rows:
                candidates = rows
                break
        candidates.sort(key=lambda item: int(item[1].get("chunk_index") or 0))
        return candidates

    @staticmethod
    def _infer_document_identity(collection: Any, document_id: str, analysis_id: str) -> tuple[str, str | int]:
        try:
            results = collection.get(where={"$and": [{"analysis_id": analysis_id}, {"document_id": document_id}]}, include=["metadatas"])
        except Exception:
            results = {"metadatas": []}
        metadatas = [m for m in results.get("metadatas") or [] if isinstance(m, dict)]
        if not metadatas:
            return "Unknown", "Unknown"
        company = next((str(m.get("company_name")) for m in metadatas if m.get("company_name") not in (None, "", "Unknown")), "Unknown")
        year_value = next((m.get("report_year") for m in metadatas if m.get("report_year") not in (None, "", "Unknown")), "Unknown")
        year: str | int = int(year_value) if str(year_value).isdigit() else str(year_value)
        return company, year

    def _extract_metrics(self, collection: Any, company_name: str, document_id: str, analysis_id: str, report_year: str | int, path: Path) -> dict[str, Any]:
        records = self._get_current_document_records(collection, company_name, document_id, analysis_id)
        if not records:
            return {}
        text = "\n\n".join(doc for doc, _ in records)
        metrics = extract_report_metrics(text, metadata=records[0][1])
        metrics.update({
            "analysis_id": analysis_id,
            "document_id": document_id,
            "company_name": company_name,
            "report_year": report_year,
            "source_text": text,
            "source": path.name,
            "source_file": path.name,
        })
        chunk_ids = [str(meta.get("chunk_id")) for _, meta in records if meta.get("chunk_id")]
        metrics["source_chunks"] = list(dict.fromkeys(chunk_ids))
        metrics["chunk_id"] = metrics["source_chunks"][0] if metrics["source_chunks"] else None
        return metrics

    def _research(self, collection: Any, analysis_id: str, company_name: str, question: str) -> dict[str, Any]:
        agent = ResearchAgent(_AnalysisScopedCollection(collection, analysis_id))
        answer = agent.answer(question, top_k=4, company=company_name)
        citations: List[Dict[str, Any]] = []
        for step in answer.steps:
            for citation in step.citations:
                citations.append({
                    "company": citation.company,
                    "doc_type": citation.doc_type,
                    "section": citation.section,
                    "source_file": citation.source_file,
                    "chunk_id": citation.chunk_id,
                    "score": citation.score,
                    "snippet": citation.snippet,
                })
        return {"answer": answer.final_answer, "evidence": citations, "sources": citations}

    def _red_flags(self, collection: Any, analysis_id: str, company_name: str) -> dict[str, Any]:
        query = f"{company_name} financial report risks financial statements performance"
        raw = collection.query(query_texts=[query], n_results=5, where={"$and": [{"analysis_id": analysis_id}, {"company_name": company_name}]}, include=["documents", "metadatas", "distances"])
        chunks = [{"document": doc, "metadata": meta or {}} for doc, meta in zip((raw.get("documents") or [[]])[0], (raw.get("metadatas") or [[]])[0])]
        gemini_service = GeminiService(api_key=os.getenv("GEMINI_API_KEY") or "")
        return RedFlagCrew(gemini_service=gemini_service).analyze(company_name, chunks)

    def _generate_report(self, extraction: dict[str, Any], research: dict[str, Any], red_flags: dict[str, Any], comparison: dict[str, Any], analysis_id: str, document_id: str, company_name: str, report_year: str | int) -> dict[str, Any]:
        return ReportAgent().generate(
            extraction=extraction,
            research=research,
            red_flags=red_flags,
            comparison=comparison,
            metadata={"analysis_id": analysis_id, "document_id": document_id, "company_name": company_name, "report_year": report_year, "chunk_id": extraction.get("chunk_id")},
        )

    def run_initial_analysis(self, report_path: str, *, analysis_id: str | None = None, document_id: str | None = None, company_name: str | None = None, report_year: int | str | None = None, question: str | None = None) -> Dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError("Document not found")
        analysis_id = analysis_id or str(uuid.uuid4())
        document_id = document_id or str(uuid.uuid4())
        ingestion = self.document_agent.ingest_document(str(path), analysis_id=analysis_id, document_id=document_id, company_name=company_name, report_year=str(report_year) if report_year is not None else None)
        if ingestion.get("status") != "success":
            raise ValueError(ingestion.get("error") or ingestion.get("message") or "Document ingestion failed")
        collection = self.document_agent.collection
        inferred_company, inferred_year = self._infer_document_identity(collection, document_id, analysis_id)
        company_name = company_name or inferred_company or path.stem
        report_year = report_year if report_year is not None else inferred_year
        question = question or f"What are the major financial developments and risks in {company_name}'s report?"
        extraction = self._extract_metrics(collection, company_name, document_id, analysis_id, report_year, path)
        research = self._research(collection, analysis_id, company_name, question)
        red_flags = self._red_flags(collection, analysis_id, company_name)
        comparison = {"comparison_type": "pending", "records": [], "summary": {"status": "pending", "message": "Comparison requires a second company document."}, "metadata": {"analysis_id": analysis_id, "document_id": document_id}}
        report = self._generate_report(extraction, research, red_flags, comparison, analysis_id, document_id, company_name, report_year)
        return {"analysis_id": analysis_id, "document_id": document_id, "company_name": company_name, "report_year": report_year, "extraction": extraction, "research": research, "red_flags": red_flags, "comparison": comparison, "report": report}

    def run_comparison_upload(self, *, analysis_id: str, original_extraction: dict[str, Any], report_path: str, document_id: str | None = None) -> dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError("Comparison document not found")
        comparison_document_id = document_id or str(uuid.uuid4())
        original_document_id = str(original_extraction.get("document_id") or "")
        if comparison_document_id == original_document_id:
            raise ValueError("Comparison document_id must differ from the original document_id")
        ingestion = self.document_agent.ingest_document(str(path), analysis_id=analysis_id, document_id=comparison_document_id)
        if ingestion.get("status") != "success":
            raise ValueError(ingestion.get("error") or ingestion.get("message") or "Comparison document ingestion failed")
        collection = self.document_agent.collection
        comparison_company, comparison_year = self._infer_document_identity(collection, comparison_document_id, analysis_id)
        if comparison_company == "Unknown":
            comparison_company = path.stem
        comparison_extraction = self._extract_metrics(collection, comparison_company, comparison_document_id, analysis_id, comparison_year, path)
        comparison = self.run_comparison(analysis_id=analysis_id, original_extraction=original_extraction, comparison_extraction=comparison_extraction)
        return {"document_id": comparison_document_id, "comparison_id": str(uuid.uuid4()), "company_name": comparison_company, "report_year": comparison_year, "extraction": comparison_extraction, "comparison": comparison}

    def run_research_query(self, analysis: Dict[str, Any], question: str) -> dict[str, Any]:
        analysis_id = str(analysis["analysis_id"])
        company_name = analysis.get("company_name") or (analysis.get("metadata") or {}).get("company_name")
        if not company_name:
            raise ValueError("Company name is unavailable for this analysis")
        return self._research(self.document_agent.collection, analysis_id, company_name, question)

    def run_red_flags_query(self, analysis: Dict[str, Any], question: str) -> dict[str, Any]:
        analysis_id = str(analysis["analysis_id"])
        company_name = analysis.get("company_name") or (analysis.get("metadata") or {}).get("company_name")
        if not company_name:
            raise ValueError("Company name is unavailable for this analysis")
        raw = self.document_agent.collection.query(query_texts=[question], n_results=5, where={"$and": [{"analysis_id": analysis_id}, {"company_name": company_name}]}, include=["documents", "metadatas", "distances"])
        chunks = [{"document": doc, "metadata": meta or {}} for doc, meta in zip((raw.get("documents") or [[]])[0], (raw.get("metadatas") or [[]])[0])]
        service = GeminiService(api_key=os.getenv("GEMINI_API_KEY") or "")
        return RedFlagCrew(gemini_service=service).analyze(company_name, chunks)

    def run_comparison(self, *, analysis_id: str, original_extraction: dict[str, Any], comparison_extraction: dict[str, Any]) -> dict[str, Any]:
        metric_keys = [("Revenue", "revenue"), ("Operating Income", "operating_income"), ("Net Income", "net_income"), ("Total Assets", "total_assets"), ("Total Liabilities", "total_liabilities"), ("Cash Flow", "cash_flow"), ("EPS", "eps")]
        records: List[dict[str, Any]] = []
        for metric_name, key in metric_keys:
            a_value = original_extraction.get(key)
            b_value = comparison_extraction.get(key)
            if a_value is None or b_value is None:
                continue
            records.append(compare_company_metrics(
                {"company_name": original_extraction.get("company_name"), "value": a_value, "metric": metric_name, "year": original_extraction.get("report_year")},
                {"company_name": comparison_extraction.get("company_name"), "value": b_value, "metric": metric_name, "year": comparison_extraction.get("report_year")},
                metric_name=metric_name,
            ))
        return {"analysis_id": analysis_id, "comparison_type": "cross_company", "companies": [original_extraction.get("company_name"), comparison_extraction.get("company_name")], "records": records, "summary": {"metrics_compared": len(records)}, "metadata": {"analysis_id": analysis_id, "document_ids": [original_extraction.get("document_id"), comparison_extraction.get("document_id")]}}

    def generate_comparison_report(self, *, analysis_id: str, original_extraction: dict[str, Any], research: dict[str, Any], red_flags: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
        return self._generate_report(original_extraction, research, red_flags, comparison, analysis_id, str(original_extraction.get("document_id")), str(original_extraction.get("company_name")), original_extraction.get("report_year") or "Unknown")

    def generate_pdf_report(self, report: dict[str, Any], output_file: str) -> str:
        from models import ExtractionData, RedFlagData, ComparisonData, ResearchItem, ReportData, RiskItem, CompanyComparison
        extraction = report.get("extraction") or {}
        extraction_data = ExtractionData(company_name=str(extraction.get("company_name") or report.get("company_name") or "Unknown"))
        for key in ("revenue", "net_income", "eps", "operating_income", "assets", "liabilities", "cash_flow"):
            value = extraction.get(key)
            if isinstance(value, (int, float)):
                setattr(extraction_data, key, value)
        red = report.get("red_flags") or {}
        risks = [RiskItem(category=str(item.get("category", "risk")), description=str(item.get("description", "")), severity=str(item.get("severity", "Medium"))) for item in (red.get("flags") or []) if isinstance(item, dict)]
        research_items = [ResearchItem(question="", answer=str(report.get("research", {}).get("answer", "")), evidence=str(item.get("snippet", "")), source=str(item.get("source_file", ""))) for item in (report.get("research", {}).get("evidence") or []) if isinstance(item, dict)]
        comparison_companies = [CompanyComparison(company_name=str(company)) for company in (report.get("comparison", {}).get("companies") or []) if company]
        report_data = ReportData(extraction=extraction_data, red_flags=RedFlagData(risks=risks), comparison=ComparisonData(companies=comparison_companies), research=research_items)
        from report_service import ReportService
        ReportService().generate(report_data, output_file)
        return output_file

    def run_analysis(self, report_path: str, company_name: str, report_year: str, question: str) -> Dict[str, Any]:
        """Legacy synchronous entry point retained for existing tests."""
        analysis_id = str(uuid.uuid4())
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{company_name}:{report_year}:{Path(report_path).name}"))
        result = self.run_initial_analysis(report_path, analysis_id=analysis_id, document_id=document_id, company_name=company_name, report_year=report_year, question=question)
        comparison = compare_report_metrics(result["extraction"])
        result["comparison"] = comparison
        result["report"] = self._generate_report(result["extraction"], result["research"], result["red_flags"], comparison, analysis_id, document_id, company_name, report_year)
        return result
