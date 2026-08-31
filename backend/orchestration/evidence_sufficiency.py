"""Evidence Sufficiency Evaluator & Controlled Research Loop.

Assesses whether retrieved evidence fulfills all mandatory nodes in the EvidenceRequirementGraph.
Formulates targeted follow-up queries when evidence is missing, with bounded iteration limits.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.orchestration.evidence_retrieval_service import (
    AdaptiveRetrievalPlanner,
    EvidenceRetrievalService,
)
from backend.orchestration.financial_fact_extractor import FinancialFactExtractor
from backend.orchestration.question_analyzer import FinancialQuestionIntent
from backend.orchestration.research_state import (
    CandidateEvidence,
    Citation,
    EvidenceRequirement,
    EvidenceRequirementGraph,
    FinancialFact,
    ResearchStep,
)

logger = logging.getLogger(__name__)


class EvidenceSufficiencyEvaluator:
    """Evaluates evidence coverage against requirements and formulates gap-targeted queries."""

    @classmethod
    def evaluate_sufficiency(
        cls,
        intent: FinancialQuestionIntent,
        extracted_facts: List[FinancialFact],
        retrieved_rows: List[Tuple[str, str, Dict[str, Any], Optional[float]]],
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Evaluate if current evidence is sufficient to answer the research question.
        Returns: (is_sufficient, missing_gap_descriptions, targeted_followup_queries)
        """
        missing_gaps: List[str] = []
        followup_queries: List[str] = []
        combined_text = " ".join(r[1] for r in retrieved_rows).lower()
        company = intent.target_company or ""
        years_str = " ".join(intent.target_years) if intent.target_years else ""

        # 1. Check entity coverage
        if intent.target_entities:
            for ent in intent.target_entities:
                has_ent = any(ent.lower() in f.entity.lower() for f in extracted_facts) or (ent.lower() in combined_text)
                if not has_ent:
                    missing_gaps.append(f"Missing financial breakdown for entity: {ent}")
                    for m in (intent.target_metrics or ["revenue"]):
                        followup_queries.append(f"{company} Total {ent} segment {m} {years_str}".strip())
                        followup_queries.append(f"{company} {ent} {m} {years_str}".strip())

        # 2. Check comparative period coverage
        if intent.is_comparative and len(intent.target_years) >= 2:
            found_periods = {f.period for f in extracted_facts}
            for yr in intent.target_years:
                if yr not in found_periods and yr not in combined_text:
                    missing_gaps.append(f"Missing comparative disclosures for period: {yr}")
                    for m in (intent.target_metrics or ["revenue"]):
                        followup_queries.append(f"{company} {m} in {yr}".strip())

        # 3. Check causal / MD&A explanatory coverage
        if intent.is_causal:
            has_mda = any(
                "discussion" in str(meta.get("section_title", "")).lower() or
                "management" in str(meta.get("section_title", "")).lower() or
                "operations" in str(meta.get("section_title", "")).lower() or
                any(kw in doc_text.lower() for kw in ["driven by", "due to", "attributed to", "primarily reflected", "cost savings", "productivity"])
                for _, doc_text, meta, _ in retrieved_rows
            )
            if not has_mda:
                missing_gaps.append("Missing management discussion of results and operational cost drivers")
                target_m = intent.target_metrics[0] if intent.target_metrics else "operating margin"
                followup_queries.append(f"{company} Management Discussion and Analysis explanation reasons drivers results operations {target_m}".strip())

        is_sufficient = len(missing_gaps) == 0
        return is_sufficient, missing_gaps, list(dict.fromkeys(followup_queries))


class ControlledResearchLoop:
    """Executes iterative retrieval, verification, and gap filling bounded by max iterations."""

    @classmethod
    def execute_research_step(
        cls,
        collection: Any,
        sub_q: str,
        top_k: int,
        intent: FinancialQuestionIntent,
        company: Optional[str] = None,
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        report_year: Optional[str | int] = None,
        max_iterations: int = 2,
    ) -> ResearchStep:
        target_company = company or intent.target_company

        # 1. Dynamic Retrieval Planning
        queries = AdaptiveRetrievalPlanner.plan_queries(intent, company_name=target_company, requirement_graph=intent.requirement_graph)

        # 2. Session Isolation Clauses
        where_clauses: List[Optional[Dict[str, Any]]] = []
        if analysis_id and target_company:
            where_clauses.append({"$and": [{"analysis_id": analysis_id}, {"company_name": target_company}]})
            where_clauses.append({"analysis_id": analysis_id})
        elif analysis_id:
            where_clauses.append({"analysis_id": analysis_id})
        else:
            if document_id:
                where_clauses.append({"document_id": document_id})
            if target_company:
                where_clauses.extend([{"company_name": target_company}, {"company": target_company}])
            where_clauses.append(None)

        # 3. Initial Multi-Query Pass
        rows = EvidenceRetrievalService.execute_retrieval_queries(collection, queries, where_clauses, target_company, top_k * 4)

        # Filter TOC/noise
        valid_rows = [r for r in rows if not EvidenceRetrievalService.is_table_of_contents_or_navigation(r[1])]
        if valid_rows:
            rows = valid_rows

        # 4. Extract facts from initial candidate rows
        initial_facts: List[FinancialFact] = []
        for cid, doc_text, meta, dist in rows:
            raw_sec = EvidenceRetrievalService.metadata_value(meta, "section_title", "section")
            section = EvidenceRetrievalService.sanitize_section_title(raw_sec, doc_text)
            page = EvidenceRetrievalService.metadata_value(meta, "page_number", "page_start", "page") or 1
            comp_name = EvidenceRetrievalService.metadata_value(meta, "company_name", "company") or target_company or "Company"
            source_file = EvidenceRetrievalService.metadata_value(meta, "source_file", "source") or "document"
            chunk_facts = FinancialFactExtractor.extract_facts_from_text(
                doc_text,
                chunk_id=str(cid),
                section=section,
                page=page,
                company=str(comp_name),
                source_file=str(source_file),
                metadata=meta,
            )
            initial_facts.extend(chunk_facts)

        # 5. Iterative Gap-Filling Loop
        iteration = 1
        all_facts = list(initial_facts)
        seen_ids = {r[0] for r in rows}

        while iteration < max_iterations:
            is_suff, gaps, gap_queries = EvidenceSufficiencyEvaluator.evaluate_sufficiency(intent, all_facts, rows)
            if is_suff or not gap_queries:
                break

            logger.info("Sufficiency gap detected: %s. Executing follow-up queries: %s", gaps, gap_queries)
            extra_rows = EvidenceRetrievalService.execute_retrieval_queries(collection, gap_queries, where_clauses, target_company, top_k * 2)
            for er in extra_rows:
                if er[0] not in seen_ids and not EvidenceRetrievalService.is_table_of_contents_or_navigation(er[1]):
                    rows.append(er)
                    seen_ids.add(er[0])
                    # Extract facts from new row
                    raw_sec = EvidenceRetrievalService.metadata_value(er[2], "section_title", "section")
                    section = EvidenceRetrievalService.sanitize_section_title(raw_sec, er[1])
                    page = EvidenceRetrievalService.metadata_value(er[2], "page_number", "page_start", "page") or 1
                    comp_name = EvidenceRetrievalService.metadata_value(er[2], "company_name", "company") or target_company or "Company"
                    source_file = EvidenceRetrievalService.metadata_value(er[2], "source_file", "source") or "document"
                    new_facts = FinancialFactExtractor.extract_facts_from_text(
                        er[1],
                        chunk_id=str(er[0]),
                        section=section,
                        page=page,
                        company=str(comp_name),
                        source_file=str(source_file),
                        metadata=er[2],
                    )
                    all_facts.extend(new_facts)

            iteration += 1

        # 6. Rank and Filter Final Evidence Set
        filtered_rows = [r for r in rows if EvidenceRetrievalService.score_candidate(r, intent, sub_q) < 1.0]
        if not filtered_rows and rows:
            filtered_rows = [r for r in rows if not EvidenceRetrievalService.is_table_of_contents_or_navigation(r[1])]

        filtered_rows.sort(key=lambda r: EvidenceRetrievalService.score_candidate(r, intent, sub_q))
        rows = filtered_rows[:max(top_k * 2, 6)]

        if not rows:
            return ResearchStep(
                sub_question=sub_q,
                findings="No indexed documents contain evidence for this. Insufficient grounded evidence was retrieved to answer this question reliably.",
                citations=[],
            )

        citations: List[Citation] = []
        seen_chunk_ids: Dict[str, Citation] = {}
        final_facts: List[FinancialFact] = []

        for cid, doc_text, meta, dist in rows:
            meta = meta or {}
            snippet = (doc_text or "")[:280] + ("…" if doc_text and len(doc_text) > 280 else "")
            company_name = EvidenceRetrievalService.metadata_value(meta, "company_name", "company") or target_company or "unknown"
            doc_type = EvidenceRetrievalService.metadata_value(meta, "doc_type", "report_type") or "Annual Report"

            raw_sec = EvidenceRetrievalService.metadata_value(meta, "section_title", "section")
            section = EvidenceRetrievalService.sanitize_section_title(raw_sec, doc_text)

            source_file = EvidenceRetrievalService.metadata_value(meta, "source_file", "source") or "document"
            chunk_id = EvidenceRetrievalService.metadata_value(meta, "chunk_id") or str(cid)
            page = EvidenceRetrievalService.metadata_value(meta, "page_number", "page_start", "page") or 1
            rep_year = EvidenceRetrievalService.metadata_value(meta, "report_year", "financial_year") or report_year

            cit = Citation(
                company=str(company_name),
                doc_type=str(doc_type),
                section=str(section),
                source_file=str(source_file),
                chunk_id=str(chunk_id),
                snippet=snippet,
                score=dist,
                page=page,
                report_year=rep_year,
            )

            if str(chunk_id) not in seen_chunk_ids:
                seen_chunk_ids[str(chunk_id)] = cit

            chunk_facts = FinancialFactExtractor.extract_facts_from_text(
                doc_text,
                chunk_id=str(chunk_id),
                section=str(section),
                page=page,
                company=str(company_name),
                source_file=str(source_file),
                metadata=meta,
            )
            final_facts.extend(chunk_facts)

        raw_texts = [doc_text for _, doc_text, _, _ in rows if doc_text]
        raw_records = [{"id": cid, "text": doc_text, "metadata": meta, "score": dist} for cid, doc_text, meta, dist in rows]
        citations = list(seen_chunk_ids.values())[:top_k * 2]

        findings_lines = [f"Top evidence retrieved for \"{sub_q}\":"]
        for cit in citations:
            findings_lines.append(f"  - \"{cit.snippet}\"  {cit}")
        findings = "\n".join(findings_lines)

        return ResearchStep(
            sub_question=sub_q,
            findings=findings,
            citations=citations,
            raw_texts=raw_texts,
            raw_records=raw_records,
            extracted_facts=final_facts,
        )
