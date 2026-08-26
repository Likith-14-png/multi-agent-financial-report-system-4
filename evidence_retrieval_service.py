"""
Evidence Retrieval Service
Targeted, reusable evidence retrieval with semantic + keyword + metadata filtering (Master Requirements §4)

Features:
- Semantic similarity search
- Keyword matching with metric aliases
- Metadata filtering (year, company, section, document)
- Section-aware retrieval (prioritize financial statements over narratives)
- Table-aware retrieval
- Document isolation guarantees
- Deterministic ordering
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalResult:
    """Single retrieved chunk with provenance."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    relevance_score: float
    retrieval_method: str  # "semantic", "keyword", "metadata"


class EvidenceRetrievalService:
    """
    Reusable service for retrieving financial evidence from ChromaDB.

    All agents (Extraction, Research, Red Flag, Comparison) use this service
    to ensure consistent, document-aware retrieval.
    """

    def __init__(self, chromadb_collection: Any):
        """Initialize with ChromaDB collection instance."""
        self.collection = chromadb_collection

    def retrieve_for_metric(
        self,
        metric_name: str,
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        doc_hash: Optional[str] = None,
        company_name: Optional[str] = None,
        year: Optional[str | int] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Retrieve evidence for a specific financial metric.

        Prioritizes exact financial statement rows over generic mentions.
        Example: "TOTAL ASSETS" (statement row) over "assets in Europe"

        Args:
            metric_name: "revenue", "total_assets", "operating_margin", etc.
            analysis_id: Restrict to specific analysis session
            document_id: Restrict to specific document
            doc_hash: Document hash for isolation
            company_name: Company name filter
            year: Report year filter
            top_k: Maximum results to return

        Returns:
            Sorted list of RetrievalResult ordered by relevance
        """
        # Build metric query variants (aliases, synonyms, table formats)
        queries = self._build_metric_queries(metric_name)

        # Build document isolation filter
        where_filter = self._build_where_filter(
            analysis_id=analysis_id,
            document_id=document_id,
            doc_hash=doc_hash,
            company_name=company_name,
            year=year,
        )

        # Execute multi-query retrieval
        results = []
        for query_text, boost in queries:
            retrieved = self.collection.query(
                query_texts=[query_text],
                n_results=top_k * 2,
                where=where_filter,
            )

            for idx, doc in enumerate(retrieved.get("documents", [[]])[0] or []):
                metadata = (retrieved.get("metadatas", [[]])[0] or [])[idx]
                distance = (retrieved.get("distances", [[]])[0] or [])[idx]

                score = (1.0 - distance) * boost  # Adjust by query boost

                result = RetrievalResult(
                    chunk_id=str(metadata.get("chunk_id", f"chunk-{idx}")),
                    text=doc or "",
                    metadata=metadata or {},
                    relevance_score=score,
                    retrieval_method="semantic",
                )
                results.append(result)

        # De-duplicate and rank by relevance
        seen = {}
        for r in sorted(results, key=lambda x: x.relevance_score, reverse=True):
            if r.chunk_id not in seen:
                seen[r.chunk_id] = r

        return list(seen.values())[:top_k]

    def retrieve_for_question(
        self,
        question: str,
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        company_name: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Retrieve evidence for an analytical question.

        Args:
            question: Natural language question
            analysis_id: Restrict to specific analysis session
            document_id: Restrict to specific document
            company_name: Company filter
            top_k: Maximum results

        Returns:
            Sorted list of RetrievalResult
        """
        where_filter = self._build_where_filter(
            analysis_id=analysis_id,
            document_id=document_id,
            company_name=company_name,
        )

        retrieved = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            where=where_filter,
        )

        results = []
        for idx, doc in enumerate(retrieved.get("documents", [[]])[0] or []):
            metadata = (retrieved.get("metadatas", [[]])[0] or [])[idx]
            distance = (retrieved.get("distances", [[]])[0] or [])[idx]

            result = RetrievalResult(
                chunk_id=str(metadata.get("chunk_id", f"chunk-{idx}")),
                text=doc or "",
                metadata=metadata or {},
                relevance_score=1.0 - distance,
                retrieval_method="semantic",
            )
            results.append(result)

        return results

    def retrieve_by_section(
        self,
        section_type: str,  # "financial_statements", "md&a", "risk", "accounting_notes"
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        company_name: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Retrieve all chunks from a specific section.

        Args:
            section_type: Type of section to retrieve
            analysis_id: Analysis ID filter
            document_id: Document filter
            company_name: Company filter
            top_k: Maximum results

        Returns:
            Chunks from specified section, in order
        """
        section_queries = self._get_section_keywords(section_type)

        where_filter = self._build_where_filter(
            analysis_id=analysis_id,
            document_id=document_id,
            company_name=company_name,
        )

        # Add section filter to where clause
        if section_type == "financial_statements":
            section_where = {
                "$and": [
                    where_filter or {},
                    {"$or": [
                        {"is_financial_table": True},
                        {"section_title": {"$regex": "balance sheet|income|cash flow"}},
                    ]},
                ]
            } if where_filter else None
        else:
            section_where = where_filter

        query_text = " ".join(section_queries)
        retrieved = self.collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where=section_where,
        )

        results = []
        for idx, doc in enumerate(retrieved.get("documents", [[]])[0] or []):
            metadata = (retrieved.get("metadatas", [[]])[0] or [])[idx]
            distance = (retrieved.get("distances", [[]])[0] or [])[idx]

            # Sort by page for deterministic ordering
            page = metadata.get("page_start") or metadata.get("page_number") or 0

            result = RetrievalResult(
                chunk_id=str(metadata.get("chunk_id", f"chunk-{idx}")),
                text=doc or "",
                metadata=metadata or {},
                relevance_score=1.0 - distance,
                retrieval_method="section",
            )
            results.append(result)

        return sorted(results, key=lambda r: (r.metadata.get("page_start", 0), r.chunk_id))[:top_k]

    @staticmethod
    def _build_metric_queries(metric_name: str) -> List[tuple[str, float]]:
        """Build list of (query_text, boost_factor) for a metric."""
        metric_lower = metric_name.lower().strip()

        # Define aliases and boost factors (higher = prioritized)
        query_variants = {
            "revenue": [
                ("Revenue from operations", 1.2),
                ("REVENUE", 1.1),
                ("Total Revenue", 1.0),
                ("sales revenue", 0.9),
                ("net sales", 0.8),
            ],
            "total_assets": [
                ("TOTAL ASSETS", 1.2),
                ("Total Assets", 1.1),
                ("Assets", 1.0),
            ],
            "operating_income": [
                ("Operating Income", 1.1),
                ("EBIT", 1.0),
                ("Operating profit", 0.9),
            ],
            "net_income": [
                ("Net Income", 1.1),
                ("Net profit", 1.0),
                ("Profit for the period", 0.9),
            ],
            "eps": [
                ("Earnings Per Share", 1.1),
                ("EPS", 1.0),
                ("diluted eps", 0.9),
            ],
            "total_debt": [
                ("Total Debt", 1.1),
                ("Total borrowings", 1.0),
                ("Long-term debt", 0.9),
            ],
            "operating_cash_flow": [
                ("Operating Cash Flow", 1.1),
                ("Cash flow from operating activities", 1.0),
                ("Operating activities", 0.9),
            ],
            "free_cash_flow": [
                ("Free Cash Flow", 1.1),
                ("FCF", 1.0),
                ("Free cash flow", 1.0),
            ],
        }

        # Return metric-specific queries, or generic fallback
        if metric_lower in query_variants:
            return query_variants[metric_lower]
        else:
            return [(metric_name, 1.0), (metric_lower, 0.9)]

    @staticmethod
    def _get_section_keywords(section_type: str) -> List[str]:
        """Get keywords for section type."""
        section_keywords = {
            "financial_statements": ["balance sheet", "income statement", "cash flow", "assets", "liabilities"],
            "md&a": ["management discussion", "analysis", "operating results", "financial position"],
            "risk": ["risks", "uncertainties", "risk factors", "material risks"],
            "accounting_notes": ["accounting policies", "notes", "significant accounting", "financial reporting"],
        }
        return section_keywords.get(section_type, [section_type])

    @staticmethod
    def _build_where_filter(
        analysis_id: Optional[str] = None,
        document_id: Optional[str] = None,
        doc_hash: Optional[str] = None,
        company_name: Optional[str] = None,
        year: Optional[str | int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Build ChromaDB where filter for document isolation.

        Ensures retrieval is restricted to specific document/company/year.
        """
        conditions = []

        # Analysis ID takes priority (strictest isolation)
        if analysis_id:
            conditions.append({"analysis_id": analysis_id})

        # Document-level isolation
        if doc_hash:
            conditions.append({"doc_hash": doc_hash})
        elif document_id:
            conditions.append({"document_id": document_id})

        # Company filter
        if company_name:
            conditions.append({"$or": [
                {"company_name": company_name},
                {"company": company_name},
            ]})

        # Year filter
        if year is not None:
            year_str = str(year).strip()
            conditions.append({"$or": [
                {"report_year": year_str},
                {"financial_year": year_str},
            ]})

        # Combine with AND
        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}
