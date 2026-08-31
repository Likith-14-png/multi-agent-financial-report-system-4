"""Adversarial & Generalization Test Suite for Question-Agnostic Financial Research Agent.

Verifies:
1. Unseen financial metrics & concepts (contract backlog, ARR, RPO, DSO, working capital, debt covenants, goodwill impairment)
2. Metric-aware calculation semantics (margin basis points vs volume growth %, CAGR, ratios, division by zero)
3. Explicit ResearchState lifecycle & provenance preservation across all pipeline stages
4. Propositional claim generation and claim-level grounding (raw question never appears in claim)
5. Multi-hop and cross-statement financial reasoning (Income statement vs Balance sheet vs MD&A)
6. Dynamic sufficiency evaluator & iterative gap-filling loop
7. Multi-tenant session isolation with analysis_id
8. Strict refusal on non-existent information without fabrication
"""
import pytest
from typing import Any, Dict, List, Optional

from backend.orchestration.research_state import (
    CalculationProof,
    Citation,
    EvidenceRequirement,
    EvidenceRequirementGraph,
    FinancialFact,
    PropositionalClaim,
    ResearchState,
    ResearchStep,
)
from backend.orchestration.financial_calculator import (
    FinancialCalculator,
    calculate_absolute_change,
    calculate_basis_point_change,
    calculate_cagr,
    calculate_growth_rate,
    calculate_margin,
    calculate_percentage_point_change,
    calculate_ratio,
    parse_numeric_value,
    verify_reported_vs_calculated,
)
from backend.orchestration.question_analyzer import (
    FinancialQuestionIntent,
    QuestionIntentAnalyzer,
    QuestionIntentType,
    StructuredResearchPlan,
)
from backend.orchestration.financial_fact_extractor import (
    ComparisonMatrix,
    FinancialFactExtractor,
    ParsedTable,
    ParsedTableRow,
    extract_facts_from_text,
    extract_tables_from_text,
)
from backend.orchestration.evidence_retrieval_service import (
    AdaptiveRetrievalPlanner,
    EvidenceRetrievalService,
)
from backend.orchestration.evidence_sufficiency import (
    ControlledResearchLoop,
    EvidenceSufficiencyEvaluator,
)
from backend.orchestration.research_reasoning_engine import FinancialReasoningEngine
from backend.orchestration.claim_validator import ClaimValidator
from research_agent import ResearchAgent, ResearchAnswer


class MockChromaGeneralizationCollection:
    """Mock ChromaDB collection for testing generalization and adversarial scenarios."""
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records
        self.recorded_queries: List[str] = []
        self.recorded_wheres: List[Optional[Dict[str, Any]]] = []

    def query(self, query_texts: List[str], n_results: int = 4, where: Optional[Dict[str, Any]] = None):
        self.recorded_queries.extend(query_texts)
        self.recorded_wheres.append(where)
        filtered = self.records
        if where is not None:
            filtered = []
            for r in self.records:
                meta = r.get("metadata", {})
                match = True
                if "$and" in where:
                    for sub in where["$and"]:
                        for k, v in sub.items():
                            if meta.get(k) != v and r.get(k) != v:
                                match = False
                else:
                    for k, v in where.items():
                        if meta.get(k) != v and r.get(k) != v:
                            match = False
                if match:
                    filtered.append(r)

        if not filtered:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        q_words = set(" ".join(query_texts).lower().split())
        def score(r):
            doc = r["document"].lower()
            meta_str = str(r.get("metadata", {})).lower()
            overlap = sum(1 for w in q_words if w in doc or w in meta_str)
            return -overlap

        sorted_records = sorted(filtered, key=score)
        return {
            "ids": [[r["id"] for r in sorted_records[:n_results]]],
            "documents": [[r["document"] for r in sorted_records[:n_results]]],
            "metadatas": [[r.get("metadata", {}) for r in sorted_records[:n_results]]],
            "distances": [[0.10 for _ in sorted_records[:n_results]]],
        }

    def get(self, include=None):
        return {"metadatas": [r.get("metadata", {}) for r in self.records]}


# ==================================================================== #
# 1. Unseen Metrics & Dynamic Intent Discovery
# ==================================================================== #
def test_dynamic_intent_unseen_financial_metrics():
    """Verify that QuestionIntentAnalyzer dynamically extracts unseen concepts without hardcoded branches."""
    questions = [
        ("What was the contract backlog and RPO at the end of 2025?", ["contract backlog", "rpo"]),
        ("Did days sales outstanding (DSO) and working capital improve between 2025 and 2024?", ["working capital", "dso"]),
        ("What is the subscription ARR and net revenue retention rate for Cloud?", ["arr", "retention rate"]),
        ("What goodwill impairment and restructuring charges were recognized?", ["impairment", "restructuring"]),
    ]

    for q, expected_metrics in questions:
        intent = QuestionIntentAnalyzer.analyze(q, target_company="Enterprise Corp")
        extracted_metrics_str = " ".join(intent.target_metrics).lower()
        for em in expected_metrics:
            assert em in extracted_metrics_str or any(em in m for m in intent.target_metrics), f"Failed to extract '{em}' from '{q}'"
        assert intent.research_plan is not None
        assert intent.requirement_graph is not None


# ==================================================================== #
# 2. Metric-Aware Calculation Semantics
# ==================================================================== #
def test_metric_aware_margin_vs_volume_calculations():
    """Verify calculation semantics: margin changes are percentage points/bps, not volume % growth."""
    # 1. Margin Percentage Point and Basis Point changes
    proof_margin = FinancialCalculator.compute_metric_change_proof(
        metric_name="operating_margin",
        entity="Cloud Division",
        curr_val=17.5,
        prev_val=16.1,
        curr_period="2025",
        prev_period="2024",
    )
    assert proof_margin.calculation_type == "margin_percentage_points"
    assert abs(proof_margin.result_val - 1.4) < 0.001
    assert "140 basis points" in proof_margin.result_formatted
    assert "+1.40 percentage points" in proof_margin.result_formatted
    assert "expanded" in proof_margin.result_formatted

    # 2. Margin contraction in basis points
    proof_margin_down = FinancialCalculator.compute_metric_change_proof(
        metric_name="gross_margin",
        entity="Hardware",
        curr_val=22.0,
        prev_val=24.5,
        curr_period="2025",
        prev_period="2024",
    )
    assert abs(proof_margin_down.result_val - (-2.5)) < 0.001
    assert "250 basis points" in proof_margin_down.result_formatted
    assert "-2.50 percentage points" in proof_margin_down.result_formatted
    assert "contracted" in proof_margin_down.result_formatted

    # 3. Revenue / Monetary volume growth rate %
    proof_rev = FinancialCalculator.compute_metric_change_proof(
        metric_name="revenue",
        entity="Software",
        curr_val=120.0,
        prev_val=100.0,
        curr_period="2025",
        prev_period="2024",
    )
    assert proof_rev.calculation_type == "growth_rate"
    assert abs(proof_rev.result_val - 20.0) < 0.001
    assert "+20.0%" in proof_rev.result_formatted
    assert "+$20" in proof_rev.result_formatted

    # 4. CAGR calculation
    cagr = FinancialCalculator.calculate_cagr(100.0, 144.0, 2)
    assert cagr is not None and abs(cagr - 20.0) < 0.001

    # 5. Division by zero protection
    assert FinancialCalculator.calculate_growth_rate(100.0, 0.0) is None
    assert FinancialCalculator.calculate_margin(100.0, 0.0) is None
    assert FinancialCalculator.calculate_ratio(100.0, 0.0) is None


# ==================================================================== #
# 3. Explicit ResearchState Provenance Tracking
# ==================================================================== #
def test_explicit_research_state_provenance():
    """Verify that ResearchAnswer produces a complete ResearchState preserving all pipeline artifacts."""
    records = [
        {
            "id": "chunk-backlog-01",
            "document": (
                "Operational Backlog & Bookings\n\n"
                "Total Contract Backlog: $18,400 million\n"
                "2024: $15,200 million\n"
                "Book-to-Bill Ratio: 1.18x\n"
            ),
            "metadata": {
                "company_name": "DefenseTech Aerospace",
                "analysis_id": "sess-state-01",
                "document_id": "doc-dt-2025",
                "section_title": "Order Backlog & Commitments",
                "source_file": "defensetech_2025.pdf",
                "chunk_id": "chunk-backlog-01",
                "page_number": 19,
                "is_financial_table": True,
            },
        }
    ]
    coll = MockChromaGeneralizationCollection(records)
    agent = ResearchAgent(coll)
    answer = agent.answer(
        "What was the total contract backlog in 2025 vs 2024 for DefenseTech Aerospace?",
        company="DefenseTech Aerospace",
        analysis_id="sess-state-01",
        document_id="doc-dt-2025",
    )

    state = answer.state
    assert state is not None
    assert state.analysis_id == "sess-state-01"
    assert state.document_id == "doc-dt-2025"
    assert state.company_name == "DefenseTech Aerospace"
    assert state.structured_facts
    # Verify fact provenance
    fact = state.structured_facts[0]
    assert fact.chunk_id == "chunk-backlog-01"
    assert fact.page == 19
    assert fact.source_file == "defensetech_2025.pdf"
    assert fact.value in [18400.0, 15200.0]


# ==================================================================== #
# 4. Claim-Level Grounding & Prevention of Raw Question Leakage
# ==================================================================== #
def test_claim_level_evidence_validation_no_question_leakage():
    """Verify that answer.evidence_claims contains propositional statements and NEVER the raw question."""
    records = [
        {
            "id": "chunk-arr-01",
            "document": (
                "Revenue & Segment Analysis\n\n"
                "Total Cloud ARR: $8,900 million\n"
                "2024: $6,800 million\n"
                "Total Professional Services: $2,100 million\n"
                "2024: $2,000 million\n"
            ),
            "metadata": {
                "company_name": "SaaS Matrix Inc",
                "analysis_id": "sess-claims-01",
                "section_title": "Revenue & Segment Analysis",
                "source_file": "saas_matrix_2025.pdf",
                "chunk_id": "chunk-arr-01",
                "page_number": 6,
                "is_financial_table": True,
            },
        }
    ]
    coll = MockChromaGeneralizationCollection(records)
    agent = ResearchAgent(coll)
    user_q = "Compare Cloud ARR and Professional Services revenue for 2025 vs 2024 and calculate growth."
    answer = agent.answer(user_q, company="SaaS Matrix Inc", analysis_id="sess-claims-01")

    assert answer.evidence_claims
    for ec in answer.evidence_claims:
        claim_text = ec.get("claim", "")
        assert claim_text != user_q, "Raw user question leaked into claim field!"
        assert user_q not in claim_text, "Raw user question found inside claim field!"
        assert "chunk_id" in ec
        assert "source_file" in ec


# ==================================================================== #
# 5. Multi-Hop Cross-Statement Financial Reasoning
# ==================================================================== #
def test_cross_statement_cash_flow_vs_net_income_reasoning():
    """Verify reasoning across Income Statement, Cash Flow Statement, and MD&A."""
    records = [
        {
            "id": "chunk-inc-stmt",
            "document": (
                "Consolidated Statements of Earnings (In millions)\n\n"
                "Net Income: 2025: $4,500 | 2024: $7,200\n"
                "Total Revenue: 2025: $48,000 | 2024: $45,000\n"
            ),
            "metadata": {
                "company_name": "Industrials Global",
                "analysis_id": "sess-multi-hop",
                "section_title": "Income Statement",
                "source_file": "industrials_2025.pdf",
                "chunk_id": "chunk-inc-stmt",
                "page_number": 45,
                "is_financial_table": True,
            },
        },
        {
            "id": "chunk-cf-stmt",
            "document": (
                "Consolidated Statements of Cash Flows (In millions)\n\n"
                "Net cash provided by operating activities: 2025: $9,800 | 2024: $8,900\n"
                "Capital expenditures: 2025: $2,100 | 2024: $1,900\n"
                "Free Cash Flow: $7,700 million\n"
            ),
            "metadata": {
                "company_name": "Industrials Global",
                "analysis_id": "sess-multi-hop",
                "section_title": "Cash Flow Statement",
                "source_file": "industrials_2025.pdf",
                "chunk_id": "chunk-cf-stmt",
                "page_number": 47,
                "is_financial_table": True,
            },
        },
        {
            "id": "chunk-mda-recon",
            "document": (
                "Management Discussion and Analysis\n\n"
                "Operating cash flow of $9,800 million remained robust and exceeded net income of $4,500 million, "
                "primarily due to significant non-cash depreciation & amortization of $3.2 billion and favorable working capital management."
            ),
            "metadata": {
                "company_name": "Industrials Global",
                "analysis_id": "sess-multi-hop",
                "section_title": "Management Discussion and Analysis",
                "source_file": "industrials_2025.pdf",
                "chunk_id": "chunk-mda-recon",
                "page_number": 28,
            },
        },
    ]
    coll = MockChromaGeneralizationCollection(records)
    agent = ResearchAgent(coll)
    answer = agent.answer(
        "What was the relationship between net income and operating cash flow in 2025, and what explains the difference?",
        company="Industrials Global",
        analysis_id="sess-multi-hop",
    )

    citations = answer.all_citations()
    c_ids = {c.chunk_id for c in citations}
    assert "chunk-inc-stmt" in c_ids or "chunk-cf-stmt" in c_ids or "chunk-mda-recon" in c_ids
    assert ("4,500" in answer.final_answer or "4500" in answer.final_answer) or ("9,800" in answer.final_answer or "9800" in answer.final_answer)


# ==================================================================== #
# 6. Sufficiency Gap-Driven Additional Retrieval Loop
# ==================================================================== #
def test_evidence_sufficiency_gap_driven_research():
    """Verify that EvidenceSufficiencyEvaluator identifies missing requirements."""
    intent = QuestionIntentAnalyzer.analyze(
        "Compare North America and EMEA revenue for 2025 vs 2024 and explain the reasons for growth.",
        target_company="OmniRetail",
    )

    # Initial facts only contain North America 2025
    initial_facts = [
        FinancialFact(
            entity="North America",
            metric="revenue",
            period="2025",
            value=15000.0,
            raw_str="$15,000M",
            chunk_id="chunk-na-2025",
        )
    ]
    initial_rows = [("chunk-na-2025", "North America revenue was $15,000 million in 2025.", {}, 0.1)]

    is_suff, gaps, followup_queries = EvidenceSufficiencyEvaluator.evaluate_sufficiency(
        intent=intent,
        extracted_facts=initial_facts,
        retrieved_rows=initial_rows,
    )

    assert is_suff is False
    assert any("emea" in g.lower() for g in gaps)
    assert any("emea" in q.lower() for q in followup_queries)


# ==================================================================== #
# 7. Multi-Tenant Session Isolation
# ==================================================================== #
def test_strict_session_isolation_across_tenants():
    """Verify multi-tenant session isolation with analysis_id."""
    records = [
        {
            "id": "tenant-alpha-chunk",
            "document": "Tenant Alpha Revenue: $1,200 million for 2025.",
            "metadata": {
                "company_name": "SharedNameCorp",
                "analysis_id": "session-alpha",
                "section_title": "Income Statement",
                "source_file": "alpha.pdf",
                "chunk_id": "tenant-alpha-chunk",
            },
        },
        {
            "id": "tenant-beta-chunk",
            "document": "Tenant Beta Revenue: $8,400 million for 2025.",
            "metadata": {
                "company_name": "SharedNameCorp",
                "analysis_id": "session-beta",
                "section_title": "Income Statement",
                "source_file": "beta.pdf",
                "chunk_id": "tenant-beta-chunk",
            },
        },
    ]
    coll = MockChromaGeneralizationCollection(records)
    agent = ResearchAgent(coll)

    # Query for Tenant Alpha session
    ans_alpha = agent.answer("What was the 2025 revenue?", company="SharedNameCorp", analysis_id="session-alpha")
    c_ids_alpha = [c.chunk_id for c in ans_alpha.all_citations()]
    assert "tenant-alpha-chunk" in c_ids_alpha
    assert "tenant-beta-chunk" not in c_ids_alpha

    # Query for Tenant Beta session
    ans_beta = agent.answer("What was the 2025 revenue?", company="SharedNameCorp", analysis_id="session-beta")
    c_ids_beta = [c.chunk_id for c in ans_beta.all_citations()]
    assert "tenant-beta-chunk" in c_ids_beta
    assert "tenant-alpha-chunk" not in c_ids_beta


# ==================================================================== #
# 8. Strict Negative Evidence Refusal
# ==================================================================== #
def test_strict_refusal_contract_on_empty_evidence():
    """Verify canonical refusal contract when no indexed evidence exists."""
    empty_coll = MockChromaGeneralizationCollection([])
    agent = ResearchAgent(empty_coll)
    answer = agent.answer("What were the quantum computing revenue streams for BioPharma Corp in 2021?", company="BioPharma Corp")

    assert "Insufficient grounded evidence was retrieved to answer this question reliably." in answer.final_answer
    assert len(answer.all_citations()) == 0
    assert len(answer.steps[0].extracted_facts) == 0


# ==================================================================== #
# 9. Multi-Signal Confidence Evaluation (Not Single Generic Score)
# ==================================================================== #
def test_multi_signal_confidence_evaluation():
    """Verify separate confidence signals: coverage, citation integrity, calculations, contradictions."""
    records = [
        {
            "id": "chunk-multi-sig-01",
            "document": (
                "Consolidated Segment Reporting (In millions)\n\n"
                "Total Cloud Revenue: 2025: $14,500 | 2024: $11,200\n"
                "Operating Margin: 2025: 18.5% | 2024: 16.0%\n"
            ),
            "metadata": {
                "company_name": "NexGen Technologies",
                "analysis_id": "sess-signals-01",
                "section_title": "Segment Reporting",
                "source_file": "nexgen_2025.pdf",
                "chunk_id": "chunk-multi-sig-01",
                "page_number": 12,
                "is_financial_table": True,
            },
        }
    ]
    coll = MockChromaGeneralizationCollection(records)
    agent = ResearchAgent(coll)
    answer = agent.answer(
        "Compare Cloud revenue and operating margin between 2025 and 2024 for NexGen Technologies.",
        company="NexGen Technologies",
        analysis_id="sess-signals-01",
    )

    # 1. Verify confidence_signals on ResearchAnswer
    signals = answer.confidence_signals
    assert signals is not None
    assert isinstance(signals.evidence_coverage, float)
    assert isinstance(signals.citation_validity, float)
    assert isinstance(signals.calculation_validity, float)
    assert signals.contradiction_status in ["none", "reconciled", "potential_conflict"]
    assert signals.overall_confidence > 0.5
    assert "Coverage:" in signals.explanation

    # 2. Verify confidence_signals serialized in to_dict()
    d = answer.to_dict(analysis_id="sess-signals-01")
    assert "confidence_signals" in d
    assert "evidence_coverage" in d["confidence_signals"]
    assert "citation_validity" in d["confidence_signals"]
    assert "calculation_validity" in d["confidence_signals"]
    assert "contradiction_status" in d["confidence_signals"]

    # 3. Verify PropositionalClaim carries confidence_signals
    assert answer.evidence_claims
    claim_dict = answer.evidence_claims[0]
    assert "confidence_signals" in claim_dict or "confidence" in claim_dict


# ==================================================================== #
# 10. High Retrieval Score Does Not Imply Truth on Gaps / Contradictions
# ==================================================================== #
def test_high_retrieval_score_does_not_imply_truth_when_gaps_exist():
    """Verify that high retrieval similarity alone does not grant 1.0 confidence when evidence has gaps."""
    # Chunk has low distance (high retrieval similarity) but only contains 2025, missing required 2024 comparison
    records = [
        {
            "id": "chunk-partial-01",
            "document": "In 2025, Semiconductor revenue reached $4,200 million.",
            "metadata": {
                "company_name": "SemiCore Corp",
                "analysis_id": "sess-gaps-01",
                "section_title": "Revenues",
                "source_file": "semicore_2025.pdf",
                "chunk_id": "chunk-partial-01",
                "page_number": 4,
            },
        }
    ]
    coll = MockChromaGeneralizationCollection(records)
    agent = ResearchAgent(coll)
    # Question asks for 2025 vs 2024 comparison for Semiconductor and Software segments
    answer = agent.answer(
        "Compare Semiconductor and Software segment revenue for 2025 vs 2024.",
        company="SemiCore Corp",
        analysis_id="sess-gaps-01",
    )

    signals = answer.confidence_signals
    assert signals is not None
    # Evidence coverage must be penalized because Software and 2024 are missing
    assert signals.evidence_coverage < 1.0
    assert len(signals.unresolved_gaps) > 0

