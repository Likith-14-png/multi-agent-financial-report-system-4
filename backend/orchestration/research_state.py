"""Research State & Data Models for Multi-Agent Financial Research System.

Maintains complete end-to-end data provenance, requirement tracking, structured facts,
deterministic calculation proofs, and claim-level evidence mappings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class Citation:
    """Document citation with exact chunk, section, and page provenance."""
    company: str
    doc_type: str
    section: str
    source_file: str
    chunk_id: str
    snippet: str
    score: Optional[float] = None
    page: Optional[int | str] = None
    report_year: Optional[int | str] = None

    def __str__(self) -> str:
        page_str = f" | Page {self.page}" if self.page else ""
        year_str = f" | {self.report_year}" if self.report_year else ""
        return (f"[{self.company} | {self.doc_type}{year_str} | {self.section} | "
                f"{self.source_file}{page_str} | chunk {self.chunk_id}]")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "company": self.company,
            "company_name": self.company,
            "doc_type": self.doc_type,
            "report_type": self.doc_type,
            "section": self.section,
            "section_title": self.section,
            "source_file": self.source_file,
            "source": self.source_file,
            "chunk_id": self.chunk_id,
            "snippet": self.snippet,
            "score": self.score,
        }
        if self.page is not None:
            d["page"] = self.page
            d["page_number"] = self.page
        if self.report_year is not None:
            d["report_year"] = self.report_year
        return d


@dataclass
class FinancialFact:
    """Structured financial fact extracted from financial statements, tables, or narrative."""
    entity: str
    metric: str
    period: str
    value: float
    raw_str: str
    unit: str = "millions"
    statement_type: str = "general"
    chunk_id: str = ""
    section: str = ""
    page: Optional[int | str] = None
    company: str = ""
    source_file: str = ""
    is_calculated: bool = False
    calculation_details: Optional[str] = None
    currency: str = "$"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "metric": self.metric,
            "period": self.period,
            "value": self.value,
            "raw_str": self.raw_str,
            "unit": self.unit,
            "statement_type": self.statement_type,
            "chunk_id": self.chunk_id,
            "section": self.section,
            "page": self.page,
            "company": self.company,
            "source_file": self.source_file,
            "is_calculated": self.is_calculated,
            "currency": self.currency,
        }


@dataclass
class EvidenceRequirement:
    """Explicit item of evidence needed to answer a research inquiry."""
    requirement_id: str
    requirement_type: str  # "metric_figure", "comparative_period", "management_narrative", "accounting_note", "risk_factor"
    description: str
    entity: Optional[str] = None
    metric: Optional[str] = None
    period: Optional[str] = None
    target_section: Optional[str] = None
    is_mandatory: bool = True
    is_satisfied: bool = False
    satisfying_chunk_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_type": self.requirement_type,
            "description": self.description,
            "entity": self.entity,
            "metric": self.metric,
            "period": self.period,
            "target_section": self.target_section,
            "is_mandatory": self.is_mandatory,
            "is_satisfied": self.is_satisfied,
            "satisfying_chunk_ids": self.satisfying_chunk_ids,
        }


@dataclass
class EvidenceRequirementGraph:
    """Graph of evidence requirements needed for comprehensive research answering."""
    requirements: List[EvidenceRequirement] = field(default_factory=list)

    def add_requirement(self, req: EvidenceRequirement) -> None:
        self.requirements.append(req)

    def get_unsatisfied(self) -> List[EvidenceRequirement]:
        return [r for r in self.requirements if not r.is_satisfied and r.is_mandatory]

    def mark_satisfied(self, req_id: str, chunk_id: str) -> None:
        for r in self.requirements:
            if r.requirement_id == req_id:
                r.is_satisfied = True
                if chunk_id not in r.satisfying_chunk_ids:
                    r.satisfying_chunk_ids.append(chunk_id)

    def completeness_ratio(self) -> float:
        if not self.requirements:
            return 1.0
        mandatory = [r for r in self.requirements if r.is_mandatory]
        if not mandatory:
            return 1.0
        satisfied = [r for r in mandatory if r.is_satisfied]
        return len(satisfied) / len(mandatory)

    def to_dict(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.requirements]


@dataclass
class CalculationProof:
    """Audit trail and exact arithmetic proof for deterministic calculations."""
    calculation_type: str  # "growth_rate", "margin_percentage_points", "margin_basis_points", "absolute_variance", "cagr", "ratio"
    metric_name: str
    entity: str
    period_current: str
    period_prior: str
    val_current: float
    val_prior: float
    result_val: float
    result_formatted: str
    formula_description: str
    source_chunk_ids: List[str] = field(default_factory=list)
    pages: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calculation_type": self.calculation_type,
            "metric_name": self.metric_name,
            "entity": self.entity,
            "period_current": self.period_current,
            "period_prior": self.period_prior,
            "val_current": self.val_current,
            "val_prior": self.val_prior,
            "result_val": self.result_val,
            "result_formatted": self.result_formatted,
            "formula_description": self.formula_description,
            "source_chunk_ids": self.source_chunk_ids,
            "pages": self.pages,
        }


@dataclass
class ConfidenceSignals:
    """Multi-signal confidence and truth evaluation.

    Confidence is NEVER a single opaque distance or retrieval score.
    It evaluates separate orthogonal signals:
    - evidence_coverage: Proportion of required entities, metrics, and periods satisfied in the EvidenceRequirementGraph
    - citation_validity: Structural correctness and completeness of source chunks, sections, and page provenance
    - calculation_validity: Mathematical consistency and proof verification without arithmetic or conversion errors
    - contradiction_status: Detection of conflicting figures across statements, restatements, or GAAP vs Non-GAAP
    """
    evidence_coverage: float = 1.0
    citation_validity: float = 1.0
    calculation_validity: float = 1.0
    contradiction_status: str = "none"  # "none", "reconciled", "potential_conflict", "unreconciled_conflict"
    unresolved_gaps: List[str] = field(default_factory=list)
    detected_conflicts: List[str] = field(default_factory=list)
    overall_confidence: float = 1.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_coverage": round(self.evidence_coverage, 2),
            "citation_validity": round(self.citation_validity, 2),
            "calculation_validity": round(self.calculation_validity, 2),
            "contradiction_status": self.contradiction_status,
            "overall_confidence": round(self.overall_confidence, 2),
            "unresolved_gaps": self.unresolved_gaps,
            "detected_conflicts": self.detected_conflicts,
            "explanation": self.explanation,
        }


@dataclass
class PropositionalClaim:
    """Individual factual claim with precise citation, period, and source backing."""
    claim_text: str
    metric: Optional[str] = None
    entity: Optional[str] = None
    period: Optional[str] = None
    numeric_value: Optional[float] = None
    calculation_proof: Optional[CalculationProof] = None
    supporting_snippet: str = ""
    source_chunk_id: str = ""
    source_file: str = ""
    page: Optional[Any] = None
    section: str = ""
    company: str = ""
    confidence: float = 1.0
    confidence_signals: Optional[ConfidenceSignals] = None
    is_verified: bool = True
    verification_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "claim": self.claim_text,
            "metric": self.metric,
            "entity": self.entity,
            "period": self.period,
            "value": self.numeric_value,
            "snippet": self.supporting_snippet,
            "source_file": self.source_file,
            "chunk_id": self.source_chunk_id,
            "page": self.page,
            "section": self.section,
            "company": self.company,
            "confidence": self.confidence,
            "is_verified": self.is_verified,
            "source": f"[{self.company} | {self.section} | {self.source_file} | Page {self.page} | chunk {self.source_chunk_id}]" if self.source_chunk_id else "",
            "calculation": self.calculation_proof.to_dict() if self.calculation_proof else None,
        }
        if self.confidence_signals:
            d["confidence_signals"] = self.confidence_signals.to_dict()
        return d


@dataclass
class CandidateEvidence:
    """Candidate passage retrieved from ChromaDB."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None
    relevance_score: float = 0.0
    is_filtered_out: bool = False
    filter_reason: Optional[str] = None


@dataclass
class ResearchStep:
    """Individual research step in query execution."""
    sub_question: str
    step_number: int = 1
    findings: str = ""
    citations: List[Citation] = field(default_factory=list)
    raw_texts: List[str] = field(default_factory=list)
    raw_records: List[Dict[str, Any]] = field(default_factory=list)
    extracted_facts: List[FinancialFact] = field(default_factory=list)
    calculations: List[CalculationProof] = field(default_factory=list)
    claims: List[PropositionalClaim] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "sub_question": self.sub_question,
            "description": self.findings or f"Evaluated evidence for '{self.sub_question}'",
            "findings": self.findings,
            "citations": [c.to_dict() for c in self.citations],
            "raw_texts": self.raw_texts,
            "extracted_facts": [f.to_dict() for f in self.extracted_facts],
            "calculations": [c.to_dict() for c in self.calculations],
        }


@dataclass
class ResearchState:
    """Complete persistent state for the research agent pipeline."""
    original_question: str
    effective_question: str
    analysis_id: Optional[str] = None
    document_id: Optional[str] = None
    company_name: Optional[str] = None
    report_year: Optional[str] = None
    intent: Optional[Any] = None
    entities: List[str] = field(default_factory=list)
    target_metrics: List[str] = field(default_factory=list)
    target_periods: List[str] = field(default_factory=list)
    statement_contexts: List[str] = field(default_factory=list)
    is_causal: bool = False
    is_comparative: bool = False
    requires_calculation: bool = False
    requires_ranking: bool = False
    requirement_graph: EvidenceRequirementGraph = field(default_factory=EvidenceRequirementGraph)
    candidate_evidence: List[CandidateEvidence] = field(default_factory=list)
    retrieved_evidence: List[CandidateEvidence] = field(default_factory=list)
    structured_facts: List[FinancialFact] = field(default_factory=list)
    comparison_matrix: Any = None
    calculations: List[CalculationProof] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_gaps: List[str] = field(default_factory=list)
    steps: List[ResearchStep] = field(default_factory=list)
    claims: List[PropositionalClaim] = field(default_factory=list)
    confidence_signals: ConfidenceSignals = field(default_factory=ConfidenceSignals)
    final_answer: Optional[str] = None
    model_used: str = "deterministic-fallback"
    is_sufficient: bool = False
    iteration_count: int = 0

    def all_citations(self) -> List[Citation]:
        best_by_chunk: Dict[str, Citation] = {}
        for step in self.steps:
            for c in step.citations:
                key = str(c.chunk_id or "").strip()
                if not key:
                    key = str((c.company, c.doc_type, c.section, c.snippet))
                existing = best_by_chunk.get(key)
                if existing is None:
                    best_by_chunk[key] = c
                    continue
                current_score = c.score if isinstance(c.score, (int, float)) else None
                existing_score = existing.score if isinstance(existing.score, (int, float)) else None
                if current_score is not None and (existing_score is None or current_score < existing_score):
                    best_by_chunk[key] = c
        return list(best_by_chunk.values())
