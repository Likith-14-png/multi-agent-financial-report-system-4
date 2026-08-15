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
if str(DOC_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(DOC_AGENT_PATH))
if str(EXTRACTION_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(EXTRACTION_AGENT_PATH))
if str(RED_FLAG_PATH) not in sys.path:
    sys.path.insert(0, str(RED_FLAG_PATH))
if str(REPORT_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(REPORT_AGENT_PATH))

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
            documents = results.get("documents") or []
            metadatas = results.get("metadatas") or []
            for doc, meta in zip(documents, metadatas):
                if not isinstance(doc, str):
                    continue
                if not isinstance(meta, dict):
                    continue
                if document_id and str(meta.get("document_id") or "") and str(meta.get("document_id")) != str(document_id):
                    continue
                candidates.append((doc, meta))
            if candidates:
                break

        if not candidates:
            return []

        candidates.sort(key=lambda item: int((item[1].get("chunk_index") if isinstance(item[1], dict) else 0) or 0))
        return candidates

    def run_analysis(self, report_path: str, company_name: str, report_year: str, question: str) -> Dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {report_path}")

        analysis_id = str(uuid.uuid4())
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{company_name}:{report_year}:{path.name}"))
        if not company_name:
            raise ValueError("company_name is required")
        if not report_year:
            raise ValueError("report_year is required")
        if not question:
            raise ValueError("question is required")

        print(f"CHROMA PATH={self.chroma_path}")
        print(f"COLLECTION NAME={self.collection_name}")
        collection = self.document_agent.collection
        print(f"COLLECTION COUNT BEFORE INGESTION={collection.count()}")
        print(f"COMPANY NAME={company_name}")
        print(f"DOCUMENT ID={document_id}")
        print(f"ANALYSIS ID={analysis_id}")

        result = self.document_agent.ingest_document(
            str(path),
            analysis_id=analysis_id,
            document_id=document_id,
            company_name=company_name,
            report_year=str(report_year),
        )
        if result.get("status") != "success":
            raise ValueError(result.get("error") or "Document ingestion failed")

        collection = self.document_agent.collection
        total_after_ingest = collection.count()
        print(f"COLLECTION COUNT AFTER INGESTION={total_after_ingest}")
        if total_after_ingest == 0:
            raise ValueError(f"Ingestion failed: collection {self.collection_name} is empty after processing {path.name}")

        sample = collection.get(limit=1, include=["documents", "metadatas"])
        print(f"FIRST INGESTED METADATA={sample.get('metadatas', [{}])[0] if sample.get('metadatas') else {}}")
        company_query = collection.query(
            query_texts=[question],
            n_results=4,
            where={"company_name": company_name},
            include=["documents", "metadatas", "distances"],
        )
        returned_docs = (company_query.get("documents") or [[]])[0]
        print(f"COMPANY FILTER RESULT COUNT={len(returned_docs)}")
        print(f"COMPANY FILTER METADATA={company_query.get('metadatas', [[]])[0]}")
        if len(returned_docs) == 0:
            raise ValueError(
                f"Company filter returned zero results for company_name={company_name} in collection={self.collection_name}. "
                "Stored metadata is incompatible with the canonical contract."
            )

        agent = ResearchAgent(collection)
        answer = agent.answer(question, top_k=4, company=company_name)

        citations: List[Dict[str, Any]] = []
        for step in answer.steps:
            for citation in step.citations:
                citation_payload = {
                    "company": citation.company,
                    "doc_type": citation.doc_type,
                    "section": citation.section,
                    "source_file": citation.source_file,
                    "chunk_id": citation.chunk_id,
                    "score": citation.score,
                    "snippet": citation.snippet,
                }
                citations.append(citation_payload)

        red_flag_query = f"{company_name} financial report risks financial statements performance"
        raw_results = collection.query(
            query_texts=[red_flag_query],
            n_results=5,
            where={"company_name": company_name},
            include=["documents", "metadatas", "distances"],
        )

        retrieved_chunks: List[Dict[str, Any]] = []
        documents = (raw_results.get("documents") or [[]])[0]
        metadatas = (raw_results.get("metadatas") or [[]])[0]
        for document, metadata in zip(documents, metadatas):
            retrieved_chunks.append({"document": document, "metadata": metadata or {}})

        gemini_service = GeminiService()
        red_flag_result = RedFlagCrew(gemini_service=gemini_service).analyze(company_name, retrieved_chunks)

        extracted_metrics = {}
        if collection is not None:
            from extraction_agent import extract_report_metrics

            current_records = self._get_current_document_records(collection, company_name, document_id)
            if current_records:
                combined_text = "\n\n".join(doc for doc, _ in current_records if isinstance(doc, str))
                first_meta = current_records[0][1] if current_records else {}
                extracted_metrics = extract_report_metrics(combined_text, metadata=first_meta)
                extracted_metrics["analysis_id"] = analysis_id
                extracted_metrics["document_id"] = document_id
                extracted_metrics["company_name"] = company_name
                extracted_metrics["report_year"] = report_year
                extracted_metrics["source_text"] = combined_text
                extracted_metrics["source"] = str(path.name)
                extracted_metrics["source_file"] = str(path.name)
                relevant_chunk_ids: List[str] = []
                for _, meta in current_records:
                    if not isinstance(meta, dict):
                        continue
                    chunk_id = meta.get("chunk_id")
                    if not chunk_id:
                        continue
                    section_title = str(meta.get("section_title") or meta.get("section") or "").strip()
                    if section_title and section_title.lower() != "unknown":
                        relevant_chunk_ids.append(str(chunk_id))
                if not relevant_chunk_ids:
                    relevant_chunk_ids = [
                        str(meta.get("chunk_id"))
                        for _, meta in current_records
                        if isinstance(meta, dict) and meta.get("chunk_id")
                    ]
                extracted_metrics["source_chunks"] = list(dict.fromkeys(str(chunk_id) for chunk_id in relevant_chunk_ids if chunk_id))
                extracted_metrics["chunk_id"] = extracted_metrics["source_chunks"][0] if extracted_metrics["source_chunks"] else None

        comparison_result = compare_report_metrics(extracted_metrics)

        report_agent = ReportAgent()
        report_result = report_agent.generate(
            extraction=extracted_metrics,
            research={"answer": answer.final_answer, "sources": citations},
            red_flags=red_flag_result,
            comparison=comparison_result,
            metadata={
                "analysis_id": analysis_id,
                "document_id": document_id,
                "company_name": company_name,
                "report_year": report_year,
                "chunk_id": None,
            },
        )

        comparison_payload = comparison_result if isinstance(comparison_result, dict) else dict(comparison_result)
        comparison_payload = comparison_result if hasattr(comparison_result, "columns") else ComparisonResult(comparison_payload)

        context = {
            "metadata": {
                "analysis_id": analysis_id,
                "document_id": document_id,
                "company_name": company_name,
                "report_year": int(report_year) if str(report_year).strip().isdigit() else report_year,
                "chunk_id": extracted_metrics.get("chunk_id") if isinstance(extracted_metrics, dict) else None,
            },
            "extraction": extracted_metrics,
            "research": {
                "answer": answer.final_answer,
                "evidence": citations,
                "sources": citations,
                "metadata": {
                    "analysis_id": analysis_id,
                    "document_id": document_id,
                    "company_name": company_name,
                    "report_year": int(report_year) if str(report_year).strip().isdigit() else report_year,
                },
            },
            "red_flags": {
                "overall_risk": red_flag_result.get("overall_risk", "Low"),
                "total_flags": int(red_flag_result.get("total_flags", 0)),
                "flags": red_flag_result.get("flags", []),
                "execution_time": float(red_flag_result.get("execution_time", 0.0)),
                "model_used": red_flag_result.get("model_used", "offline-fallback"),
                "metadata": {
                    "analysis_id": analysis_id,
                    "document_id": document_id,
                    "company_name": company_name,
                    "report_year": int(report_year) if str(report_year).strip().isdigit() else report_year,
                },
            },
            "comparison": comparison_payload,
            "report": report_result,
        }

        validated_context = validate_analysis_context(context)
        response = {
            "status": "success",
            "analysis": validated_context.model_dump(mode="json"),
            "metadata": context["metadata"],
            "analysis_id": analysis_id,
            "document_id": document_id,
            "company_name": company_name,
            "report_year": str(report_year),
            "extraction": extracted_metrics,
            "research": context["research"],
            "red_flags": context["red_flags"],
            "comparison": comparison_payload,
            "report": report_result,
            "answer": answer.final_answer,
            "sources": citations,
        }

        return response
