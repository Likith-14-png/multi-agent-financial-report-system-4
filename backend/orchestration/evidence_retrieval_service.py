"""Adaptive Multi-Query Evidence Retrieval Service.

Plans and executes targeted ChromaDB multi-query retrieval passes with:
- Session isolation & multi-tenant security
- Dynamic query reformulation driven by the EvidenceRequirementGraph
- Domain-aware relevance scoring & noise/TOC rejection
- Section title sanitization & metadata recovery
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.orchestration.question_analyzer import FinancialQuestionIntent
from backend.orchestration.research_state import (
    CandidateEvidence,
    Citation,
    EvidenceRequirement,
    EvidenceRequirementGraph,
)

logger = logging.getLogger(__name__)


class AdaptiveRetrievalPlanner:
    """Generates orthogonal, requirement-targeted ChromaDB queries from the Evidence Requirement Graph."""

    @classmethod
    def plan_queries(
        cls,
        intent: FinancialQuestionIntent,
        company_name: Optional[str] = None,
        requirement_graph: Optional[EvidenceRequirementGraph] = None,
    ) -> List[str]:
        queries: List[str] = [intent.original_question]
        comp = f"{company_name} " if company_name else ""
        years_str = " ".join(intent.target_years) if intent.target_years else ""

        # 1. Generate queries for explicit entities and segment breakdowns
        if intent.target_entities:
            entities_str = " ".join(intent.target_entities)
            for m in (intent.target_metrics or ["revenue"]):
                queries.append(f"{comp}{entities_str} {m} breakdown {years_str}".strip())
                queries.append(f"{comp}Revenue & Segment Analysis {entities_str} {years_str}".strip())
                for ent in intent.target_entities:
                    queries.append(f"{comp}Total {ent} {m} {years_str}".strip())
        elif "segment" in intent.target_metrics or "segment" in intent.original_question.lower():
            queries.append(f"{comp}segment revenue breakdown {years_str}".strip())
            queries.append(f"{comp}Revenue & Segment Analysis business segments results".strip())

        # 2. Generate statement-specific queries from target metrics
        for metric in intent.target_metrics:
            m_low = metric.lower()
            if any(w in m_low for w in ["margin", "profitability"]):
                queries.append(f"{comp}operating margin operating profit margin gross margin expansion contraction drivers")
                queries.append(f"{comp}Management Discussion and Analysis reasons factors drivers operating margin changes")
                queries.append(f"{comp}Consolidated Statement of Operations operating income revenue operating margin")
            elif any(w in m_low for w in ["cash flow", "fcf", "operating cash flow"]):
                queries.append(f"{comp}Statement of Cash Flows Free Cash Flow operating activities capital expenditures")
            elif any(w in m_low for w in ["debt", "liabilities", "equity", "balance sheet", "working capital"]):
                queries.append(f"{comp}Consolidated Balance Sheet Total debt liabilities stockholders equity {metric}")
            elif any(w in m_low for w in ["eps", "earnings per share"]):
                queries.append(f"{comp}diluted earnings per share basic EPS continuing operations per share")
            elif any(w in m_low for w in ["risk", "going concern", "stress"]):
                queries.append(f"{comp}Risk Factors principal risks liquidity debt going concern customer concentration")
            else:
                # Dynamic query formulation for any arbitrary metric
                queries.append(f"{comp}{metric} {years_str}".strip())
                queries.append(f"{comp}financial statements {metric} {years_str}".strip())

        # 3. Generate MD&A / Causal explanatory queries
        if intent.is_causal or any(w in intent.original_question.lower() for w in ["why", "cause", "driver", "reason", "impact", "factor"]):
            metrics_focus = " ".join(intent.target_metrics) if intent.target_metrics else "results of operations"
            queries.append(f"{comp}Management Discussion and Analysis results of operations drivers {metrics_focus} explanation")
            queries.append(f"{comp}factors contributing to increase decrease changes in profitability expenses largest impact")

        # 4. Generate queries from unsatisfied requirements in requirement_graph
        if requirement_graph:
            for req in requirement_graph.get_unsatisfied():
                if req.requirement_type == "metric_figure" and req.metric:
                    ent_prefix = f"{req.entity} " if req.entity else ""
                    yr_suffix = f" {req.period}" if req.period else ""
                    queries.append(f"{comp}{ent_prefix}{req.metric}{yr_suffix}".strip())
                elif req.requirement_type == "management_narrative":
                    queries.append(f"{comp}Management Discussion and Analysis operational performance cost drivers")

        return list(dict.fromkeys(queries))


class EvidenceRetrievalService:
    """Orchestrates ChromaDB queries, session isolation, noise filtering, and candidate ranking."""

    @staticmethod
    def is_table_of_contents_or_navigation(text: str) -> bool:
        """Detect and reject Table of Contents, index pages, or navigation text."""
        if not text or not text.strip():
            return True
        t = text.lower().strip()
        if "table of contents" in t and ("item 1" in t or "page" in t or "...." in t or "part i" in t):
            return True
        if t.count("....") >= 2 or t.count(". . . .") >= 2:
            return True
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 3 and all(re.search(r"item\s+\d+|page\s+\d+|\.{3,}", l, re.I) for l in lines[:3]):
            return True
        return False

    @staticmethod
    def infer_section_from_text(text: Optional[str]) -> Optional[str]:
        if not isinstance(text, str) or not text.strip():
            return None
        patterns = [
            (r"(?im)^\s*(?:\d+[.)]\s*)?Revenue & Segment Analysis\b", "Revenue & Segment Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Management Discussion and Analysis\b", "Management Discussion and Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Liquidity and Capital Resources\b", "Liquidity and Capital Resources"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Risk Factors\b", "Risk Factors"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Balance Sheet\b", "Balance Sheet"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Income Statement\b", "Income Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Consolidated Statement of Operations\b", "Income Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Cash Flow Statement\b", "Cash Flow Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Consolidated Statement of Cash Flows\b", "Cash Flow Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Notes to the Financial Statements\b", "Notes to the Financial Statements"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Profitability & Performance Metrics\b", "Profitability & Performance Metrics"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Segment Analysis\b", "Segment Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Financing & Debt\b", "Financing & Debt"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Auditor'?s Report\b", "Auditor's Report"),
        ]
        for pattern, title in patterns:
            if re.search(pattern, text):
                return title
        return None

    @classmethod
    def sanitize_section_title(cls, raw_section: Any, doc_text: str) -> str:
        """Sanitize junk numeric headers like '(95)', '4,116', '0.02' into meaningful section names."""
        if raw_section is None:
            raw_str = ""
        else:
            raw_str = str(raw_section).strip()

        is_junk = (
            not raw_str or
            raw_str.lower() in {"unknown", "n/a", "na", "none", "null"} or
            re.match(r"^[\(\$\d,\.\)\s\-]+$", raw_str) or
            len(raw_str) < 3
        )

        if is_junk:
            inferred = cls.infer_section_from_text(doc_text)
            if inferred:
                return inferred
            low = doc_text.lower()
            if "segment" in low or "division" in low or "breakdown" in low or "line of business" in low:
                return "Revenue & Segment Analysis"
            if "cash flow" in low or "operating activities" in low:
                return "Cash Flow Statement"
            if "balance sheet" in low or "total assets" in low or "stockholders' equity" in low:
                return "Balance Sheet"
            if "income statement" in low or "net income" in low or "diluted eps" in low or "statement of operations" in low:
                return "Income Statement"
            if "management discussion" in low or "results of operations" in low:
                return "Management Discussion and Analysis"
            if "risk factors" in low or "principal risks" in low:
                return "Risk Factors"
            return "Financial Overview"

        return raw_str

    @staticmethod
    def normalize_company_name(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        text = re.sub(r"\s+", " ", text)
        return text.casefold()

    @staticmethod
    def is_missing_metadata_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned == "":
                return True
            lowered = cleaned.lower()
            return lowered in {"unknown", "n/a", "na", "not available", "unavailable", "none", "null"}
        return False

    @classmethod
    def metadata_value(cls, metadata: Optional[Dict[str, Any]], *keys: str) -> Any:
        if not isinstance(metadata, dict):
            return None
        for key in keys:
            value = metadata.get(key)
            if not cls.is_missing_metadata_value(value):
                return value
        return None

    @classmethod
    def matches_company_name(cls, target_company: Optional[str], metadata: Optional[Dict[str, Any]]) -> bool:
        if not target_company:
            return True
        target_norm = cls.normalize_company_name(target_company)
        if not target_norm:
            return True
        candidates = [
            cls.metadata_value(metadata, "company_name"),
            cls.metadata_value(metadata, "company"),
        ]
        for candidate in candidates:
            if cls.normalize_company_name(candidate) == target_norm:
                return True
        return False

    @staticmethod
    def rows_from_query_results(results: Optional[Dict[str, Any]]) -> List[Tuple[str, str, Dict[str, Any], Optional[float]]]:
        if not results:
            return []
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[None] * len(ids)])[0]
        rows: List[Tuple[str, str, Dict[str, Any], Optional[float]]] = []
        for cid, doc_text, meta, dist in zip(ids, docs, metas, dists):
            rows.append((str(cid), doc_text or "", meta or {}, dist))
        return rows

    @classmethod
    def score_candidate(
        cls,
        row: Tuple[str, str, Dict[str, Any], Optional[float]],
        intent: FinancialQuestionIntent,
        sub_q: str,
    ) -> float:
        """Domain-aware relevance score combining cosine distance, entity, metric, and statement fit."""
        _, doc_text, meta, dist = row
        score = float(dist) if dist is not None else 0.5
        text_low = (doc_text or "").lower()
        sec_title = str(meta.get("section_title", "")).lower()
        sec_type = str(meta.get("section_type", "")).lower()

        if cls.is_table_of_contents_or_navigation(doc_text):
            return 999.0

        # Entity Matching Boost
        if intent.target_entities:
            matching_ents = sum(1 for ent in intent.target_entities if ent.lower() in text_low)
            if matching_ents >= 2:
                score -= 0.50
            elif matching_ents == 1:
                score -= 0.25
            if any(st in sec_title for st in ["revenue & segment analysis", "segment analysis", "segment", "revenue", "breakdown"]):
                score -= 0.30

        # Statement & Metric Compatibility
        is_margin_q = any(m in ["operating margin", "profit margin", "gross margin"] for m in intent.target_metrics) or "margin" in sub_q.lower()
        is_debt_q = any(m in ["debt", "total debt", "liabilities", "equity", "balance sheet"] for m in intent.target_metrics) or "debt" in sub_q.lower()
        is_cash_q = any(m in ["cash flow", "free cash flow", "operating cash flow"] for m in intent.target_metrics) or "cash flow" in sub_q.lower()

        if is_margin_q:
            if any(w in text_low for w in ["operating margin", "gross margin", "margin", "operating profit", "operating income", "cost of revenue", "sg&a", "r&d", "operating expense", "profitability"]):
                score -= 0.40
            if any(w in text_low for w in ["driven by", "due to", "attributed to", "primarily reflected", "cost savings", "productivity"]):
                score -= 0.30
            if any(b in sec_title for b in ["balance sheet", "financial position", "liabilities", "cash flow"]):
                score += 1.50
            if ("total liabilities" in text_low or "cash and cash equivalents" in text_low) and "margin" not in text_low:
                score += 1.20

        elif is_debt_q:
            if any(w in text_low for w in ["debt", "liabilities", "stockholders", "equity", "borrowing", "balance sheet"]):
                score -= 0.35
            if "cash flow statement" in sec_title and "debt" not in text_low:
                score += 1.00

        elif is_cash_q:
            if any(w in text_low for w in ["cash flow", "operating activities", "free cash flow", "capex"]):
                score -= 0.35
            if "balance sheet" in sec_title and "cash flow" not in text_low:
                score += 1.00

        # Analytical & MD&A Section Boost
        if intent.is_causal or any(w in sub_q.lower() for w in ["why", "driver", "cause", "reason", "impact", "factor"]):
            if sec_type in {"management_discussion", "business", "summary"} or "discussion" in sec_title or "review" in sec_title or "operations" in sec_title:
                score -= 0.30

        if meta.get("is_financial_table") or meta.get("is_table") or "(in millions)" in text_low:
            if not intent.is_causal:
                score -= 0.20

        return score

    @classmethod
    def execute_retrieval_queries(
        cls,
        collection: Any,
        queries: List[str],
        where_clauses: List[Optional[Dict[str, Any]]],
        target_company: Optional[str],
        n_results: int,
    ) -> List[Tuple[str, str, Dict[str, Any], Optional[float]]]:
        """Execute single/multi-query searches against ChromaDB with session isolation."""
        rows: List[Tuple[str, str, Dict[str, Any], Optional[float]]] = []
        retrieved_ids = set()
        for q_text in queries:
            for where in where_clauses:
                try:
                    results = collection.query(
                        query_texts=[q_text],
                        n_results=n_results,
                        where=where,
                    ) if collection is not None else None
                except Exception:
                    results = None

                candidate_rows = cls.rows_from_query_results(results)
                for cid, doc_text, meta, dist in candidate_rows:
                    if cid not in retrieved_ids:
                        if cls.matches_company_name(target_company, meta):
                            rows.append((cid, doc_text, meta, dist))
                            retrieved_ids.add(cid)
        return rows
