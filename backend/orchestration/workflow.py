from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DOC_AGENT_PATH = ROOT / "document-agent-text-chunking" / "scripts"
EXTRACTION_AGENT_PATH = ROOT / "extraction-agent"
RED_FLAG_PATH = ROOT / "red_flag_agent"
REPORT_AGENT_PATH = ROOT / "report-agent"
for path in (DOC_AGENT_PATH, EXTRACTION_AGENT_PATH, RED_FLAG_PATH, REPORT_AGENT_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from document_agent import DocumentAgent, DocumentAgentConfig
from research_agent import ResearchAgent
from compare import ComparisonResult, compare_report_metrics
from app.agents.crew import RedFlagCrew
from app.services.gemini_service import GeminiService
from report_agent import ReportAgent
from backend.orchestration.contract import validate_analysis_context


class AnalysisWorkflow:
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
    def _get_current_document_records(collection: Any, company_name: str, document_id: str) -> List[tuple[str, Dict[str, Any]]]:
        if collection is None:
            return []
        candidates: List[tuple[str, Dict[str, Any]]] = []
        for where in (
            {"$and": [{"company_name": company_name}, {"document_id": document_id}]},
            {"company_name": company_name},
        ):
            try:
                results = collection.get(where=where, include=["documents", "metadatas"])
            except Exception:
                continue
            for doc, meta in zip(results.get("documents") or [], results.get("metadatas") or []):
                if isinstance(doc, str) and isinstance(meta, dict):
                    if document_id and str(meta.get("document_id") or "") and str(meta.get("document_id")) != str(document_id):
                        continue
                    candidates.append((doc, meta))
            if candidates:
                break
        candidates.sort(key=lambda item: int((item[1].get("chunk_index") or 0)))
        return candidates

    def _extract_metrics(self, collection: Any, company_name: str, document_id: str, analysis_id: str, report_year: int | str, path: Path) -> dict[str, Any]:
        from extraction_agent import extract_report_metrics
        records = self._get_current_document_records(collection, company_name, document_id)
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

    def _research(self, collection: Any, company_name: str, question: str) -> tuple[dict[str, Any], ResearchAgent]:
        agent = ResearchAgent(collection)
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
        return {"answer": answer.final_answer, "evidence": citations, "sources": citations}, agent

    def _red_flags(self, collection: Any, company_name: str) -> dict[str, Any]:
        query = f"{company_name} financial report risks financial statements performance"
        raw = collection.query(query_texts=[query], n_results=5, where={"company_name": company_name}, include=["documents", "metadatas", "distances"])
        chunks = [
            {"document": doc, "metadata": meta or {}}
            for doc, meta in zip((raw.get("documents") or [[]])[0], (raw.get("metadatas") or [[]])[0])
        ]
        # Explicitly read the environment at call time. This preserves the
        # existing Red Flag Agent fallback behavior when tests remove the key.
        gemini_service = GeminiService(api_key=os.getenv("GEMINI_API_KEY") or "")
        return RedFlagCrew(gemini_service=gemini_service).analyze(company_name, chunks)

    def run_initial_analysis(
        self,
        report_path: str,
        *,
        analysis_id: str | None = None,
        document_id: str | None = None,
        company_name: str | None = None,
        report_year: int | str | None = None,
        question: str | None = None,
    ) -> Dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError("Document not found")
        analysis_id = analysis_id or str(uuid.uuid4())
        document_id = document_id or str(uuid.uuid4())
        company_name = company_name or path.stem
        report_year = report_year or "Unknown"
        question = question or f"What are the major financial developments and risks in {company_name}'s report?"

        self.document_agent.ingest_document(str(path), analysis_id=analysis_id, document_id=document_id, company_name=company_name, report_year=str(report_year))
        collection = self.document_agent.collection
        extraction = self._extract_metrics(collection, company_name, document_id, analysis_id, report_year, path)
        research, _ = self._research(collection, company_name, question)
        red_flags = self._red_flags(collection, company_name)
        comparison = {"comparison_type": "pending", "records": [], "summary": {}, "metadata": {"analysis_id": analysis_id, "document_id": document_id}}
        report = ReportAgent().generate(
            extraction=extraction,
            research=research,
            red_flags=red_flags,
            comparison=comparison,
            metadata={"analysis_id": analysis_id, "document_id": document_id, "company_name": company_name, "report_year": report_year, "chunk_id": extraction.get("chunk_id")},
        )
        return {"analysis_id": analysis_id, "document_id": document_id, "company_name": company_name, "report_year": report_year, "extraction": extraction, "research": research, "red_flags": red_flags, "comparison": comparison, "report": report}

    def run_research_query(self, analysis: Dict[str, Any], question: str) -> dict[str, Any]:
        collection = self.document_agent.collection
        company_name = analysis.get("company_name") or analysis.get("metadata", {}).get("company_name")
        result, _ = self._research(collection, company_name, question)
        return result

    def run_red_flags_query(self, analysis: Dict[str, Any], question: str) -> dict[str, Any]:
        collection = self.document_agent.collection
        company_name = analysis.get("company_name") or analysis.get("metadata", {}).get("company_name")
        # Reuse the existing risk-agent flow; the question only controls retrieval.
        raw = collection.query(query_texts=[question], n_results=5, where={"company_name": company_name}, include=["documents", "metadatas", "distances"])
        chunks = [{"document": doc, "metadata": meta or {}} for doc, meta in zip((raw.get("documents") or [[]])[0], (raw.get("metadatas") or [[]])[0])]
        service = GeminiService(api_key=os.getenv("GEMINI_API_KEY") or "")
        return RedFlagCrew(gemini_service=service).analyze(company_name, chunks)

    def run_comparison(
        self,
        *,
        analysis_id: str,
        original_extraction: dict[str, Any],
        comparison_extraction: dict[str, Any],
    ) -> dict[str, Any]:
        # The existing compare implementation is the sole comparison logic.
        from compare import compare_company_metrics
        companies = [original_extraction, comparison_extraction]
        records = []
        for metric in ("Revenue", "Operating Income", "Net Income", "Total Assets", "Total Liabilities", "Cash Flow", "EPS"):
            a = {"company_name": original_extraction.get("company_name"), "value": original_extraction.get(metric.lower().replace(" ", "_")), "metric": metric}
            b = {"company_name": comparison_extraction.get("company_name"), "value": comparison_extraction.get(metric.lower().replace(" ", "_")), "metric": metric}
            if a["value"] is None and b["value"] is None:
                continue
            records.append(compare_company_metrics(a, b, metric_name=metric))
        return {"analysis_id": analysis_id, "companies": [c.get("company_name") for c in companies], "records": records, "summary": {"metrics_compared": len(records)}, "metadata": {"document_ids": [original_extraction.get("document_id"), comparison_extraction.get("document_id")]}}

    def generate_pdf_report(self, report: dict[str, Any], output_file: str) -> str:
        from models import ExtractionData, RedFlagData, ComparisonData, ResearchItem, ReportData, RiskItem, CompanyComparison
        extraction = report.get("extraction") or {}
        extraction_data = ExtractionData(company_name=extraction.get("company_name") or "Unknown", revenue=None)
        for key in ("revenue", "net_income", "eps", "operating_income", "assets", "liabilities", "cash_flow"):
            if key in extraction and isinstance(extraction[key], (int, float)):
                setattr(extraction_data, key, extraction[key])
        red = report.get("red_flags") or {}
        risks = [RiskItem(category=str(x.get("category", "risk")), description=str(x.get("description", "")), severity=str(x.get("severity", "Medium"))) for x in red.get("flags", []) if isinstance(x, dict)]
        research = [ResearchItem(question="", answer=str(report.get("research", {}).get("answer", "")), evidence=str(x.get("snippet", "")), source=str(x.get("source_file", ""))) for x in report.get("research", {}).get("evidence", []) if isinstance(x, dict)]
        comparison = ComparisonData(companies=[])
        report_data = ReportData(extraction=extraction_data, red_flags=RedFlagData(risks=risks), comparison=comparison, research=research)
        from report_service import ReportService
        ReportService().generate(report_data, output_file)
        return output_file

    def run_analysis(self, report_path: str, company_name: str, report_year: str, question: str) -> Dict[str, Any]:
        """Legacy synchronous entry point retained for existing tests."""
        analysis_id = str(uuid.uuid4())
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{company_name}:{report_year}:{Path(report_path).name}"))
        result = self.run_initial_analysis(report_path, analysis_id=analysis_id, document_id=document_id, company_name=company_name, report_year=report_year, question=question)
        # Legacy tests expect year-over-year comparison during the legacy path.
        comparison = compare_report_metrics(result["extraction"])
        result["comparison"] = comparison
        result["report"] = ReportAgent().generate(extraction=result["extraction"], research=result["research"], red_flags=result["red_flags"], comparison=comparison, metadata={"analysis_id": analysis_id, "document_id": document_id, "company_name": company_name, "report_year": report_year, "chunk_id": result["extraction"].get("chunk_id")})
        context = {"metadata": {"analysis_id": analysis_id, "document_id": document_id, "company_name": company_name, "report_year": int(report_year) if str(report_year).isdigit() else report_year, "chunk_id": result["extraction"].get("chunk_id")}, "extraction": result["extraction"], "research": result["research"], "red_flags": result["red_flags"], "comparison": result["comparison"], "report": result["report"]}
        validated = validate_analysis_context(context)
        result["analysis"] = validated.model_dump(mode="json")
        result["metadata"] = context["metadata"]
        result["status"] = "success"
        result["answer"] = result["research"].get("answer", "")
        result["sources"] = result["research"].get("sources", [])
        return result
