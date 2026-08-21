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
if str(DOC_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(DOC_AGENT_PATH))
if str(EXTRACTION_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(EXTRACTION_AGENT_PATH))
if str(RED_FLAG_PATH) not in sys.path:
    sys.path.insert(0, str(RED_FLAG_PATH))
if str(REPORT_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(REPORT_AGENT_PATH))

from document_agent import DocumentAgent, DocumentAgentConfig
from extraction_agent import extract_report_metrics
from research_agent import ResearchAgent
from compare import ComparisonResult, compare_company_metrics, compare_report_metrics
from app.agents.crew import RedFlagCrew
from app.services.gemini_service import GeminiService
from report_agent import ReportAgent
from report_service import ReportService
from models import (
    ReportData,
    ExtractionData,
    RedFlagData,
    RiskItem,
    ComparisonData,
    CompanyComparison,
    ResearchItem,
)
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

    def run_document_ingestion(
        self,
        report_path: str,
        company_name: Optional[str] = None,
        report_year: Optional[str | int] = None,
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {report_path}")

        current_analysis_id = analysis_id or str(uuid.uuid4())
        doc_seed = f"{company_name or 'unknown'}:{report_year or 'unknown'}:{path.name}"
        doc_id = document_id or str(uuid.uuid5(uuid.NAMESPACE_URL, doc_seed))

        ingest_kwargs: Dict[str, Any] = {
            "analysis_id": current_analysis_id,
            "document_id": doc_id,
        }
        if company_name:
            ingest_kwargs["company_name"] = str(company_name).strip()
        if report_year:
            ingest_kwargs["report_year"] = str(report_year).strip()

        result = self.document_agent.ingest_document(str(path), **ingest_kwargs)
        if result.get("status") != "success":
            raise ValueError(result.get("error") or "Document ingestion failed")

        collection = self.document_agent.collection
        sample = collection.get(where={"document_id": doc_id}, include=["documents", "metadatas"])
        docs = sample.get("documents") or []
        metas = sample.get("metadatas") or []
        ids = sample.get("ids") or []

        if not docs:
            sample = collection.get(where={"analysis_id": current_analysis_id}, include=["documents", "metadatas"])
            docs = sample.get("documents") or []
            metas = sample.get("metadatas") or []
            ids = sample.get("ids") or []

        first_meta = metas[0] if metas and isinstance(metas[0], dict) else {}
        effective_company_name = company_name or first_meta.get("company_name") or "Unknown Company"
        effective_report_year = str(report_year or first_meta.get("report_year") or "2025")

        chunk_records = []
        for idx, (cid, doc_text, meta) in enumerate(zip(ids, docs, metas)):
            meta_dict = meta if isinstance(meta, dict) else {}
            chunk_records.append({
                "chunk_id": str(meta_dict.get("chunk_id") or cid),
                "chunk_index": int(meta_dict.get("chunk_index", idx)),
                "page_number": meta_dict.get("page_number", "1"),
                "page_start": int(meta_dict.get("page_start", 1)) if meta_dict.get("page_start") is not None else 1,
                "page_end": int(meta_dict.get("page_end", 1)) if meta_dict.get("page_end") is not None else 1,
                "section_title": meta_dict.get("section_title", "Unknown"),
                "section_type": meta_dict.get("section_type", "other"),
                "text": doc_text,
                "metadata": meta_dict,
            })

        chunk_records.sort(key=lambda c: c["chunk_index"])

        return {
            "status": "success",
            "message": "Document processed and stored in ChromaDB successfully",
            "analysis_id": current_analysis_id,
            "document_id": doc_id,
            "company_name": effective_company_name,
            "report_year": effective_report_year,
            "document": path.name,
            "collection": self.collection_name,
            "total_chunks": len(chunk_records),
            "chunks": chunk_records,
            "quality_report": result.get("quality_report") or {},
            "metadata": {
                "analysis_id": current_analysis_id,
                "document_id": doc_id,
                "company_name": effective_company_name,
                "report_year": effective_report_year,
                "source": path.name,
                "collection": self.collection_name,
                "total_chunks": len(chunk_records),
            },
        }

    def run_extraction(
        self,
        analysis_id: str,
        company_name: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        collection = self.document_agent.collection
        current_records = self._get_current_document_records(collection, company_name or "", document_id or "")
        if not current_records:
            sample = collection.get(where={"analysis_id": analysis_id}, include=["documents", "metadatas"])
            docs = sample.get("documents") or []
            metas = sample.get("metadatas") or []
            current_records = list(zip(docs, metas))

        if current_records:
            chunk_records = []
            for idx, (doc, meta) in enumerate(current_records):
                meta_dict = meta if isinstance(meta, dict) else {}
                chunk_records.append({
                    "chunk_id": str(meta_dict.get("chunk_id") or f"chunk-{idx}"),
                    "chunk_index": int(meta_dict.get("chunk_index", idx)),
                    "page_start": int(meta_dict.get("page_start", 1)) if meta_dict.get("page_start") is not None else 1,
                    "page_end": int(meta_dict.get("page_end", 1)) if meta_dict.get("page_end") is not None else 1,
                    "section_title": meta_dict.get("section_title", "Unknown"),
                    "text": doc,
                    "metadata": meta_dict,
                })
            combined_text = "\n\n".join(doc for doc, _ in current_records if isinstance(doc, str))
            doc_meta = current_records[0][1] if current_records else {}
            extracted_metrics = extract_report_metrics(combined_text, metadata=doc_meta, chunk_records=chunk_records)
        else:
            extracted_metrics = extract_report_metrics("", metadata={})

        first_meta = current_records[0][1] if current_records and isinstance(current_records[0][1], dict) else {}
        effective_company_name = company_name or extracted_metrics.get("company_name") or first_meta.get("company_name") or "Unknown Company"
        effective_report_year = str(extracted_metrics.get("report_year") or first_meta.get("report_year") or "2025")
        source_name = first_meta.get("source") or first_meta.get("source_file") or "document"

        extracted_metrics["analysis_id"] = analysis_id
        extracted_metrics["document_id"] = document_id or str(first_meta.get("document_id") or "")
        extracted_metrics["company_name"] = effective_company_name
        extracted_metrics["report_year"] = effective_report_year
        extracted_metrics["source_text"] = combined_text if current_records else ""
        extracted_metrics["source"] = source_name
        extracted_metrics["source_file"] = source_name

        relevant_chunk_ids: List[str] = []
        for _, meta in current_records:
            if isinstance(meta, dict) and meta.get("chunk_id"):
                relevant_chunk_ids.append(str(meta["chunk_id"]))
        extracted_metrics["source_chunks"] = list(dict.fromkeys(relevant_chunk_ids))
        extracted_metrics["chunk_id"] = extracted_metrics["source_chunks"][0] if extracted_metrics["source_chunks"] else None

        return extracted_metrics

    def run_research(
        self,
        analysis_id: str,
        company_name: Optional[str] = None,
        question: Optional[str] = None,
        document_id: Optional[str] = None,
        report_year: Optional[str | int] = None,
    ) -> Dict[str, Any]:
        effective_question = question.strip() if question and str(question).strip() else "What are the major financial developments and risks in this report?"
        collection = self.document_agent.collection
        agent = ResearchAgent(collection)
        answer = agent.answer(
            effective_question,
            top_k=4,
            company=company_name,
            analysis_id=analysis_id,
            document_id=document_id,
            report_year=report_year,
        )
        return answer.to_dict(analysis_id=analysis_id)

    def run_red_flags(
        self,
        analysis_id: str,
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        effective_company_name = company_name or "Company"
        collection = self.document_agent.collection
        company_filter = {"company_name": effective_company_name} if effective_company_name else None
        red_flag_query = f"{effective_company_name} financial report risks financial statements performance"
        try:
            raw_results = collection.query(
                query_texts=[red_flag_query],
                n_results=5,
                where=company_filter,
                include=["documents", "metadatas", "distances"],
            )
            docs = (raw_results.get("documents") or [[]])[0]
            metas = (raw_results.get("metadatas") or [[]])[0]
        except Exception:
            docs, metas = [], []

        retrieved_chunks: List[Dict[str, Any]] = []
        for document, metadata in zip(docs, metas):
            retrieved_chunks.append({"document": document, "metadata": metadata or {}})

        api_key = os.getenv("GEMINI_API_KEY")
        gemini_service = GeminiService(api_key=api_key or "")
        if not api_key:
            gemini_service.api_key = ""

        red_flag_result = RedFlagCrew(gemini_service=gemini_service).analyze(effective_company_name, retrieved_chunks)
        red_flag_result["analysis_id"] = analysis_id
        return red_flag_result

    def run_report(
        self,
        analysis_id: str,
        company_name: Optional[str] = None,
        report_year: Optional[str | int] = None,
        document_id: Optional[str] = None,
        extraction: Optional[Dict[str, Any]] = None,
        research: Optional[Dict[str, Any]] = None,
        red_flags: Optional[Dict[str, Any]] = None,
        comparison: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ext = extraction or self.run_extraction(analysis_id, company_name=company_name, document_id=document_id)
        effective_company = company_name or ext.get("company_name") or "Company"
        effective_year = str(report_year or ext.get("report_year") or "2025")
        doc_id = document_id or ext.get("document_id") or str(uuid.uuid4())

        res = research or self.run_research(analysis_id, company_name=effective_company)
        rf = red_flags or self.run_red_flags(analysis_id, company_name=effective_company)
        cmp = comparison or compare_report_metrics(ext)

        report_agent = ReportAgent()
        report_result = report_agent.generate(
            extraction=ext,
            research={
                "answer": res.get("answer") or res.get("summary") or "",
                "sources": res.get("sources") or res.get("evidence") or [],
                "evidence": res.get("evidence") or res.get("sources") or [],
            },
            red_flags=rf,
            comparison=cmp,
            metadata={
                "analysis_id": analysis_id,
                "document_id": doc_id,
                "company_name": effective_company,
                "report_year": effective_year,
                "chunk_id": ext.get("chunk_id"),
            },
        )
        return report_result

    def run_analysis(
        self,
        report_path: str,
        company_name: Optional[str] = None,
        report_year: Optional[str | int] = None,
        question: Optional[str] = None,
        analysis_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {report_path}")

        current_analysis_id = analysis_id or str(uuid.uuid4())
        doc_seed = f"{company_name or 'unknown'}:{report_year or 'unknown'}:{path.name}"
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, doc_seed))

        # Default research question if omitted
        effective_question = question.strip() if question and str(question).strip() else "What are the major financial developments and risks in this report?"

        ingest_kwargs: Dict[str, Any] = {
            "analysis_id": current_analysis_id,
            "document_id": document_id,
        }
        if company_name:
            ingest_kwargs["company_name"] = str(company_name).strip()
        if report_year:
            ingest_kwargs["report_year"] = str(report_year).strip()

        result = self.document_agent.ingest_document(str(path), **ingest_kwargs)
        if result.get("status") != "success":
            raise ValueError(result.get("error") or "Document ingestion failed")

        collection = self.document_agent.collection
        total_after_ingest = collection.count()
        if total_after_ingest == 0:
            raise ValueError(f"Ingestion failed: collection {self.collection_name} is empty after processing {path.name}")

        # If company_name or report_year were not provided, detect from ingested chunks for THIS document
        sample = collection.get(where={"document_id": document_id}, include=["documents", "metadatas"])
        metadatas = sample.get("metadatas") or []
        first_meta = metadatas[0] if metadatas and isinstance(metadatas[0], dict) else {}

        effective_company_name = company_name or first_meta.get("company_name") or "Unknown Company"
        effective_report_year = str(report_year or first_meta.get("report_year") or "2025")

        # 1. Research Agent
        company_filter = {"company_name": effective_company_name} if effective_company_name else None
        try:
            company_query = collection.query(
                query_texts=[effective_question],
                n_results=4,
                where=company_filter,
                include=["documents", "metadatas", "distances"],
            )
            returned_docs = (company_query.get("documents") or [[]])[0]
        except Exception:
            returned_docs = []

        agent = ResearchAgent(collection)
        answer = agent.answer(
            effective_question,
            top_k=4,
            company=effective_company_name,
            analysis_id=current_analysis_id,
            document_id=document_id,
            report_year=effective_report_year,
        )
        research_dict = answer.to_dict(analysis_id=current_analysis_id)
        citations = research_dict["sources"]

        # 2. Red Flag Agent (Respect dynamic GEMINI_API_KEY environment status)
        red_flag_query = f"{effective_company_name} financial report risks financial statements performance"
        try:
            raw_results = collection.query(
                query_texts=[red_flag_query],
                n_results=5,
                where=company_filter,
                include=["documents", "metadatas", "distances"],
            )
            docs = (raw_results.get("documents") or [[]])[0]
            metas = (raw_results.get("metadatas") or [[]])[0]
        except Exception:
            docs, metas = [], []

        retrieved_chunks: List[Dict[str, Any]] = []
        for document, metadata in zip(docs, metas):
            retrieved_chunks.append({"document": document, "metadata": metadata or {}})

        # Explicitly pass current runtime environment key to prevent falling back to stale module-level constants
        api_key = os.getenv("GEMINI_API_KEY")
        gemini_service = GeminiService(api_key=api_key or "")
        if not api_key:
            gemini_service.api_key = ""

        red_flag_result = RedFlagCrew(gemini_service=gemini_service).analyze(effective_company_name, retrieved_chunks)

        # 3. Extraction Agent
        extracted_metrics: Dict[str, Any] = {}
        current_records = self._get_current_document_records(collection, effective_company_name, document_id)
        if current_records:
            combined_text = "\n\n".join(doc for doc, _ in current_records if isinstance(doc, str))
            doc_meta = current_records[0][1] if current_records else {}
            extracted_metrics = extract_report_metrics(combined_text, metadata=doc_meta)
        else:
            sample_docs = sample.get("documents") or []
            combined_text = "\n\n".join(doc for doc in sample_docs if isinstance(doc, str))
            extracted_metrics = extract_report_metrics(combined_text, metadata=first_meta)

        extracted_metrics["analysis_id"] = current_analysis_id
        extracted_metrics["document_id"] = document_id
        extracted_metrics["company_name"] = effective_company_name
        extracted_metrics["report_year"] = effective_report_year
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

        # 4. Yearly trend calculations (for internal report agent contract)
        single_doc_comparison = compare_report_metrics(extracted_metrics)

        # 5. Report Agent
        report_agent = ReportAgent()
        report_result = report_agent.generate(
            extraction=extracted_metrics,
            research={"answer": answer.final_answer, "sources": citations},
            red_flags=red_flag_result,
            comparison=single_doc_comparison,
            metadata={
                "analysis_id": current_analysis_id,
                "document_id": document_id,
                "company_name": effective_company_name,
                "report_year": effective_report_year,
                "chunk_id": extracted_metrics.get("chunk_id"),
            },
        )

        comparison_payload = single_doc_comparison if isinstance(single_doc_comparison, dict) else dict(single_doc_comparison)
        comparison_payload = single_doc_comparison if hasattr(single_doc_comparison, "columns") else ComparisonResult(comparison_payload)

        context = {
            "metadata": {
                "analysis_id": current_analysis_id,
                "document_id": document_id,
                "company_name": effective_company_name,
                "report_year": int(effective_report_year) if str(effective_report_year).strip().isdigit() else effective_report_year,
                "chunk_id": extracted_metrics.get("chunk_id"),
            },
            "extraction": extracted_metrics,
            "research": {
                "answer": answer.final_answer,
                "evidence": citations,
                "sources": citations,
                "metadata": {
                    "analysis_id": current_analysis_id,
                    "document_id": document_id,
                    "company_name": effective_company_name,
                    "report_year": int(effective_report_year) if str(effective_report_year).strip().isdigit() else effective_report_year,
                },
            },
            "red_flags": {
                "overall_risk": red_flag_result.get("overall_risk", "Low"),
                "total_flags": int(red_flag_result.get("total_flags", 0)),
                "flags": red_flag_result.get("flags", []),
                "execution_time": float(red_flag_result.get("execution_time", 0.0)),
                "model_used": red_flag_result.get("model_used", "offline-fallback"),
                "metadata": {
                    "analysis_id": current_analysis_id,
                    "document_id": document_id,
                    "company_name": effective_company_name,
                    "report_year": int(effective_report_year) if str(effective_report_year).strip().isdigit() else effective_report_year,
                },
            },
            "comparison": comparison_payload,
            "report": report_result,
        }

        validated_context = validate_analysis_context(context)
        response = {
            "status": "success",
            "success": True,
            "analysis": validated_context.model_dump(mode="json"),
            "metadata": context["metadata"],
            "analysis_id": current_analysis_id,
            "document_id": document_id,
            "company_name": effective_company_name,
            "report_year": str(effective_report_year),
            "extraction": extracted_metrics,
            "research": context["research"],
            "red_flags": context["red_flags"],
            "comparison": comparison_payload,
            "report": report_result,
            "answer": answer.final_answer,
            "sources": citations,
        }

        return response

    def run_research_query(
        self,
        analysis_id: str,
        question: str,
        company_name: Optional[str] = None,
        document_id: Optional[str] = None,
        report_year: Optional[str | int] = None,
    ) -> Dict[str, Any]:
        """Execute a follow-up query against the existing ChromaDB collection using ResearchAgent."""
        effective_question = question.strip() if question and str(question).strip() else "What are the major financial developments and risks in this report?"
        collection = self.document_agent.collection
        agent = ResearchAgent(collection)
        answer = agent.answer(
            effective_question,
            top_k=4,
            company=company_name,
            analysis_id=analysis_id,
            document_id=document_id,
            report_year=report_year,
        )
        return answer.to_dict(analysis_id=analysis_id)

    def run_red_flags_query(self, analysis_id: str, question: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        """Execute a risk/red-flag specific query grounded in ChromaDB document evidence."""
        collection = self.document_agent.collection
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

        return {
            "analysis_id": analysis_id,
            "question": question,
            "answer": answer.final_answer,
            "sources": citations,
        }

    def run_comparison(
        self,
        analysis_id: str,
        first_company_name: str,
        first_extracted: Dict[str, Any],
        second_report_path: str,
        second_company_name: Optional[str] = None,
        second_report_year: Optional[str | int] = None,
    ) -> Dict[str, Any]:
        """Process a second company's report and perform cross-company comparison."""
        path_b = Path(second_report_path)
        if not path_b.exists():
            raise FileNotFoundError(f"Second document not found: {second_report_path}")

        comp_seed = f"{second_company_name or path_b.stem}:{second_report_year or '2025'}:{path_b.name}"
        second_document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"comp:{analysis_id}:{comp_seed}"))
        comparison_id = f"cmp-{uuid.uuid4().hex[:8]}"

        # Ingest second document with its own document_id under the same analysis_id
        ingest_kwargs: Dict[str, Any] = {
            "analysis_id": analysis_id,
            "document_id": second_document_id,
        }
        if second_company_name:
            ingest_kwargs["company_name"] = str(second_company_name).strip()
        if second_report_year:
            ingest_kwargs["report_year"] = str(second_report_year).strip()

        result_b = self.document_agent.ingest_document(str(path_b), **ingest_kwargs)
        if result_b.get("status") != "success":
            raise ValueError(result_b.get("error") or "Second document ingestion failed")

        collection = self.document_agent.collection
        records_b = self._get_current_document_records(collection, second_company_name or "", second_document_id)
        if not records_b:
            sample = collection.get(limit=10, include=["documents", "metadatas"])
            metas = sample.get("metadatas") or []
            matching_indices = [
                i for i, m in enumerate(metas)
                if isinstance(m, dict) and m.get("document_id") == second_document_id
            ]
            if matching_indices:
                records_b = [(sample["documents"][i], metas[i]) for i in matching_indices]
            else:
                records_b = [(sample["documents"][0], metas[0])] if sample.get("documents") else []

        combined_text_b = "\n\n".join(doc for doc, _ in records_b if isinstance(doc, str))
        meta_b = records_b[0][1] if records_b else {}
        extracted_b = extract_report_metrics(combined_text_b, metadata=meta_b)

        effective_b_name = second_company_name or extracted_b.get("company_name") or meta_b.get("company_name") or path_b.stem

        # Execute metric comparisons across Company A and Company B
        metric_keys = [
            ("Revenue", "revenue"),
            ("Operating Income", "operating_income"),
            ("Net Income", "net_income"),
            ("Total Assets", "total_assets"),
            ("Total Liabilities", "total_liabilities"),
            ("Cash Flow", "cash_flow"),
            ("EPS", "eps"),
        ]

        comparison_records: List[Dict[str, Any]] = []
        for label, key in metric_keys:
            val_a = first_extracted.get(key)
            val_b = extracted_b.get(key)
            res = compare_company_metrics(
                {"company_name": first_company_name, "metric": label, "value": val_a},
                {"company_name": effective_b_name, "metric": label, "value": val_b},
                metric_name=label,
            )
            comparison_records.append(res)

        return {
            "analysis_id": analysis_id,
            "comparison_id": comparison_id,
            "status": "completed",
            "companies": [first_company_name, effective_b_name],
            "comparison_document_id": second_document_id,
            "metrics": comparison_records,
            "records": comparison_records,
            "summary": {
                "companies_compared": [first_company_name, effective_b_name],
                "metrics_analyzed": len(comparison_records),
                "company_a": first_company_name,
                "company_b": effective_b_name,
            },
        }

    def generate_pdf_report(self, session_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Generate PDF report using existing ReportService and PDFBuilder."""
        ext_dict = session_data.get("extraction_result") or {}
        red_dict = session_data.get("red_flags_result") or {}
        res_dict = session_data.get("research_result") or {}
        cmp_dict = session_data.get("comparison_result") or {}

        def _safe_float(val: Any) -> Optional[float]:
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            import re
            m = re.search(r"[-+]?\d+(?:\.\d+)?", str(val).replace(",", ""))
            return float(m.group(0)) if m else None

        extraction = ExtractionData(
            company_name=session_data.get("company_name") or ext_dict.get("company_name") or "Company",
            revenue=_safe_float(ext_dict.get("revenue")),
            net_profit=_safe_float(ext_dict.get("net_income")),
            eps=_safe_float(ext_dict.get("eps")),
            assets=_safe_float(ext_dict.get("total_assets")),
            liabilities=_safe_float(ext_dict.get("total_liabilities")),
            cash_flow=_safe_float(ext_dict.get("cash_flow")),
        )

        risk_items: List[RiskItem] = []
        for flag in (red_dict.get("flags") or []):
            if isinstance(flag, dict):
                risk_items.append(
                    RiskItem(
                        category=flag.get("category") or "Financial",
                        description=flag.get("description") or flag.get("title") or "Risk identified",
                        severity=flag.get("severity") or "Medium",
                    )
                )
        red_flags = RedFlagData(risks=risk_items)

        comp_companies: List[CompanyComparison] = []
        if cmp_dict and cmp_dict.get("companies"):
            for comp_name in cmp_dict["companies"]:
                comp_companies.append(CompanyComparison(company_name=comp_name))
        comparison = ComparisonData(companies=comp_companies)

        research_items: List[ResearchItem] = []
        answer_text = res_dict.get("answer") or "Financial analysis completed."
        sources = res_dict.get("sources") or []
        evidence_text = sources[0].get("snippet", "Evidence retrieved.") if sources and isinstance(sources[0], dict) else "Evidence retrieved."
        source_text = sources[0].get("source_file", "Annual Report") if sources and isinstance(sources[0], dict) else "Annual Report"

        research_items.append(
            ResearchItem(
                question="What are the key financial performance highlights?",
                answer=answer_text,
                evidence=evidence_text,
                source=source_text,
            )
        )

        report_data = ReportData(
            extraction=extraction,
            red_flags=red_flags,
            comparison=comparison,
            research=research_items,
        )

        service = ReportService()
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = output_path or str(output_dir / f"financial_report_{session_data.get('analysis_id', 'session')}.pdf")

        service.generate(report_data, pdf_file)
        return pdf_file
