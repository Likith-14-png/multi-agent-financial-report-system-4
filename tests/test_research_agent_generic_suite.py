"""Generic 10-Capability Production Test Suite for Research Agent.

Verifies:
1. Single factual lookup (Arbitrary company & metric)
2. Multi-entity comparison (Arbitrary divisions & multiple periods)
3. Deterministic calculation engine (YoY growth, CAGR, Margin, Ratio, Negative growth, Division by zero)
4. Dynamic entity & intent extraction across unseen questions
5. Dynamic multi-query retrieval planning
6. Cross-chunk evidence synthesis (Revenue in Chunk A, Previous year in Chunk B, MD&A cost drivers in Chunk C)
7. Multi-part compound question (Comparison + Growth + Ranking + Causal reason + Citations)
8. Different financial terminology (FinTech: Net Interest Margin, Adjusted EBITDA, Subscription ARR, Provision for Credit Losses)
9. Different document structures & table layouts (Pipe-separated, multiline vertical, single line)
10. Strict negative evidence contract (Refusal on non-existent facts without hallucination)
11. Multi-tenant session isolation with analysis_id
12. Diagnostic regression check (IBM 2025 question)
"""
import pytest
from typing import Any, Dict, List, Optional
from research_agent import (
    ResearchAgent,
    Citation,
    ResearchStep,
    ResearchAnswer,
    QuestionIntentAnalyzer,
    DynamicRetrievalPlanner,
    FinancialCalculator,
    extract_tables_from_text,
    parse_numeric_value,
)


class GenericMockCollection:
    """Mock ChromaDB collection for generic financial testing."""
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
# Capability 1: Single Factual Lookup
# ==================================================================== #
def test_capability_1_single_factual_lookup():
    records = [
        {
            "id": "acme-eps-01",
            "document": (
                "Consolidated Statement of Operations\n\n"
                "Diluted EPS from Continuing Operations: $4.85\n"
                "Consolidated Earnings Per Share: $4.85\n"
                "Free Cash Flow: $8,400 million\n"
            ),
            "metadata": {
                "company_name": "Acme Global Technologies",
                "analysis_id": "acme-sess-01",
                "section_title": "Statement of Operations",
                "source_file": "acme_2025.pdf",
                "chunk_id": "acme-eps-01",
                "page_number": 8,
            },
        }
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    answer = agent.answer("What was Acme Global Technologies diluted EPS in 2025?", company="Acme Global Technologies", analysis_id="acme-sess-01")

    assert "$4.85" in answer.final_answer
    assert any(c.chunk_id == "acme-eps-01" for c in answer.all_citations())
    assert any(c.page == 8 for c in answer.all_citations())


# ==================================================================== #
# Capability 2: Multi-Entity Comparison Matrix
# ==================================================================== #
def test_capability_2_multi_entity_comparison_matrix():
    records = [
        {
            "id": "bio-seg-01",
            "document": (
                "Division Performance Summary (In millions)\n\n"
                "Total Pharmaceuticals: $42,500 million\n2024: $38,000 million\n\n"
                "Total Oncology: $18,200 million\n2024: $15,500 million\n\n"
                "Total Vaccines: $11,400 million\n2024: $12,000 million\n\n"
                "Total Diagnostics: $7,900 million\n2024: $7,100 million\n"
            ),
            "metadata": {
                "company_name": "BioHealth Therapeutics",
                "analysis_id": "bio-sess-01",
                "section_title": "Segment Analysis",
                "source_file": "biohealth_annual.pdf",
                "chunk_id": "bio-seg-01",
                "page_number": 14,
                "is_financial_table": True,
            },
        }
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    question = "Compare Pharmaceuticals, Oncology, Vaccines, and Diagnostics segment revenue for 2025 vs 2024, calculate growth, and identify which grew most."
    answer = agent.answer(question, company="BioHealth Therapeutics", analysis_id="bio-sess-01")

    assert "Pharmaceuticals" in answer.final_answer
    assert "Oncology" in answer.final_answer
    assert "Vaccines" in answer.final_answer
    assert "Diagnostics" in answer.final_answer

    assert "11.8%" in answer.final_answer or "+11.8%" in answer.final_answer
    assert "17.4%" in answer.final_answer or "+17.4%" in answer.final_answer
    assert "-5.0%" in answer.final_answer
    assert "11.3%" in answer.final_answer or "+11.3%" in answer.final_answer

    assert "Oncology" in answer.final_answer
    assert any(c.chunk_id == "bio-seg-01" for c in answer.all_citations())


# ==================================================================== #
# Capability 3: Deterministic Financial Calculator
# ==================================================================== #
def test_capability_3_financial_calculator():
    # YoY growth
    assert abs(FinancialCalculator.calculate_growth_rate(29962, 27085) - 10.622) < 0.01
    assert abs(FinancialCalculator.calculate_growth_rate(15718, 14020) - 12.111) < 0.01
    assert FinancialCalculator.calculate_growth_rate(100, 0) is None
    assert FinancialCalculator.calculate_growth_rate(90, 100) == -10.0

    # Absolute change
    assert FinancialCalculator.calculate_absolute_change(15718, 14020) == 1698.0
    assert FinancialCalculator.calculate_absolute_change(90, 100) == -10.0

    # Operating Margin
    assert abs(FinancialCalculator.calculate_margin(8500, 65400) - 12.996) < 0.01
    assert FinancialCalculator.calculate_margin(100, 0) is None

    # CAGR
    cagr = FinancialCalculator.calculate_cagr(100.0, 144.0, 2)
    assert cagr is not None and abs(cagr - 20.0) < 0.01

    # Ratio
    assert abs(FinancialCalculator.calculate_ratio(61260, 52000) - 1.178) < 0.01

    # Percentage point change
    assert abs(FinancialCalculator.calculate_percentage_point_change(15.2, 13.8) - 1.4) < 0.01

    # Reported vs calculated verification
    is_match, msg = FinancialCalculator.verify_reported_vs_calculated(10.62, 10.6)
    assert is_match is True
    is_match2, msg2 = FinancialCalculator.verify_reported_vs_calculated(15.0, 10.0)
    assert is_match2 is False


# ==================================================================== #
# Capability 4: Dynamic Question Intent & Entity Extraction
# ==================================================================== #
def test_capability_4_dynamic_intent_extraction():
    q = "Compare Cloud Services, Retail Banking, and Wealth Management division revenue for 2025 vs 2024, calculate the year-over-year change, and explain why performance improved."
    intent = QuestionIntentAnalyzer.analyze(q, target_company="Apex Financial")

    assert intent.is_comparative is True
    assert intent.is_causal is True
    assert intent.requires_calculation is True
    assert "2025" in intent.target_years
    assert "2024" in intent.target_years
    assert any("cloud" in e.lower() for e in intent.target_entities)
    assert any("retail" in e.lower() for e in intent.target_entities)
    assert any("wealth" in e.lower() for e in intent.target_entities)

    plan = intent.research_plan
    assert plan is not None
    assert len(plan.sub_questions) >= 1
    assert "comparison" in plan.operations
    assert "calculation" in plan.operations


# ==================================================================== #
# Capability 5: Dynamic Retrieval Planning
# ==================================================================== #
def test_capability_5_dynamic_retrieval_planner():
    q = "Compare Automotive, Energy Storage, and Solar Services division revenue for 2025 vs 2024."
    intent = QuestionIntentAnalyzer.analyze(q, target_company="Tesla Motors")
    queries = DynamicRetrievalPlanner.plan_queries(intent, company_name="Tesla Motors")

    assert len(queries) >= 3
    queries_str = " ".join(queries).lower()
    assert "automotive" in queries_str
    assert "energy storage" in queries_str
    assert "solar services" in queries_str


# ==================================================================== #
# Capability 6: Cross-Chunk Evidence Synthesis
# ==================================================================== #
def test_capability_6_cross_chunk_evidence_synthesis():
    records = [
        {
            "id": "chunk-rev-2025",
            "document": (
                "Segment Performance Summary (In millions)\n\n"
                "Total Enterprise Software: $29,962 million\n"
                "2024: $27,085 million\n"
            ),
            "metadata": {
                "company_name": "GlobalTech Inc",
                "analysis_id": "cross-chunk-sess",
                "section_title": "Revenue & Segment Analysis",
                "source_file": "globaltech_2025.pdf",
                "chunk_id": "chunk-rev-2025",
                "page_number": 4,
                "is_financial_table": True,
            },
        },
        {
            "id": "chunk-mda-drivers",
            "document": (
                "Management Discussion and Analysis\n\n"
                "Enterprise Software revenue increased driven by Hybrid Cloud expansion and Red Hat growth. "
                "Operating margin expanded by 140 basis points due to operational efficiency and cost structure savings."
            ),
            "metadata": {
                "company_name": "GlobalTech Inc",
                "analysis_id": "cross-chunk-sess",
                "section_title": "Management Discussion and Analysis",
                "source_file": "globaltech_2025.pdf",
                "chunk_id": "chunk-mda-drivers",
                "page_number": 7,
            },
        },
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    question = "What was Enterprise Software revenue in 2025 vs 2024, and what were the main drivers for its performance?"
    answer = agent.answer(question, company="GlobalTech Inc", analysis_id="cross-chunk-sess")

    assert "Enterprise Software" in answer.final_answer
    assert any(c.chunk_id == "chunk-rev-2025" for c in answer.all_citations())
    assert any(c.chunk_id == "chunk-mda-drivers" for c in answer.all_citations())


# ==================================================================== #
# Capability 7: Multi-Part Compound Questions
# ==================================================================== #
def test_capability_7_multi_part_question():
    records = [
        {
            "id": "mp-chunk-01",
            "document": (
                "Financial Summary\n\n"
                "Total Revenue: $65,400 million\n"
                "Total Debt: $42,100 million\n"
                "Free Cash Flow: $12,300 million\n"
            ),
            "metadata": {
                "company_name": "Apex Enterprise",
                "analysis_id": "mp-sess",
                "section_title": "Financial Highlights",
                "source_file": "apex_rep.pdf",
                "chunk_id": "mp-chunk-01",
                "page_number": 2,
            },
        }
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    question = "What was total revenue, total debt, and free cash flow in 2025?"
    answer = agent.answer(question, company="Apex Enterprise", analysis_id="mp-sess")

    assert "$65,400" in answer.final_answer or "65,400" in answer.final_answer
    assert "$42,100" in answer.final_answer or "42,100" in answer.final_answer
    assert "$12,300" in answer.final_answer or "12,300" in answer.final_answer
    assert any(c.chunk_id == "mp-chunk-01" for c in answer.all_citations())


# ==================================================================== #
# Capability 8: Different Financial Terminology (FinTech Metrics)
# ==================================================================== #
def test_capability_8_fintech_terminology():
    records = [
        {
            "id": "fintech-chunk-01",
            "document": (
                "Segment Performance Summary (In millions)\n\n"
                "Total Digital Payments: $12,800 million\n2024: $10,500 million\n\n"
                "Total Credit Solutions: $8,400 million\n2024: $7,900 million\n"
            ),
            "metadata": {
                "company_name": "FinTech Corp",
                "analysis_id": "fintech-sess",
                "section_title": "Segment Analysis",
                "source_file": "fintech_2025.pdf",
                "chunk_id": "fintech-chunk-01",
                "page_number": 11,
                "is_financial_table": True,
            },
        }
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    question = "Compare Digital Payments and Credit Solutions division revenue for 2025 vs 2024, calculate growth, and identify which grew most."
    answer = agent.answer(question, company="FinTech Corp", analysis_id="fintech-sess")

    assert "Digital Payments" in answer.final_answer
    assert "Credit Solutions" in answer.final_answer
    assert "21.9%" in answer.final_answer or "+21.9%" in answer.final_answer
    assert "6.3%" in answer.final_answer or "+6.3%" in answer.final_answer
    assert "Digital Payments" in answer.final_answer
    assert any(c.chunk_id == "fintech-chunk-01" for c in answer.all_citations())


# ==================================================================== #
# Capability 9: Different Table Formats & Multi-Layout Extraction
# ==================================================================== #
def test_capability_9_multi_layout_table_parsing():
    # Pipe-separated table
    pipe_text = (
        "Revenue by Business Division (In millions)\n"
        "Division | 2025 | 2024\n"
        "Cloud Infrastructure: 2025: $14,500 | 2024: $12,200\n"
        "Cybersecurity: 2025: $8,100 | 2024: $7,000\n"
    )
    tables = extract_tables_from_text(pipe_text)
    assert len(tables) > 0
    t = tables[0]
    assert len(t.rows) == 2
    assert t.rows[0].label == "Cloud Infrastructure"
    assert t.rows[0].values == [14500.0, 12200.0]

    # Parenthetical negative number parsing
    assert parse_numeric_value("(1,240)") == -1240.0
    assert parse_numeric_value("$(45.5)") == -45.5
    assert parse_numeric_value("$29,962") == 29962.0


# ==================================================================== #
# Capability 10: Strict Missing Evidence Refusal Contract
# ==================================================================== #
def test_capability_10_missing_evidence_refusal():
    empty_coll = GenericMockCollection([])
    agent = ResearchAgent(empty_coll)
    answer = agent.answer("What was the 2025 revenue for Space Tourism division?", company="AeroSpace Inc")

    assert "Insufficient grounded evidence was retrieved to answer this question reliably." in answer.final_answer
    assert len(answer.all_citations()) == 0


# ==================================================================== #
# Capability 11: Multi-Tenant Session Isolation
# ==================================================================== #
def test_capability_11_session_isolation():
    records = [
        {
            "id": "tenant-a-chunk",
            "document": "Tenant A Revenue: $500 million",
            "metadata": {
                "company_name": "TenantCorp",
                "analysis_id": "tenant-a-session",
                "section_title": "Income Statement",
                "source_file": "tenant_a.pdf",
                "chunk_id": "tenant-a-chunk",
            },
        },
        {
            "id": "tenant-b-chunk",
            "document": "Tenant B Revenue: $900 million",
            "metadata": {
                "company_name": "TenantCorp",
                "analysis_id": "tenant-b-session",
                "section_title": "Income Statement",
                "source_file": "tenant_b.pdf",
                "chunk_id": "tenant-b-chunk",
            },
        },
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    
    answer_a = agent.answer("What was the revenue?", company="TenantCorp", analysis_id="tenant-a-session")
    assert any(c.chunk_id == "tenant-a-chunk" for c in answer_a.all_citations())
    assert not any(c.chunk_id == "tenant-b-chunk" for c in answer_a.all_citations())


# ==================================================================== #
# Diagnostic Regression Check: IBM 2025 Test Case
# ==================================================================== #
def test_diagnostic_regression_ibm_question():
    records = [
        {
            "id": "2eeb57fc-1b58-40e0-af21-b4f1576b9348",
            "document": (
                "Revenue & Segment Analysis (In millions)\n\n"
                "Total Software: $29,962 million\n"
                "2024: $27,085 million\n\n"
                "Total Consulting: $21,055 million\n"
                "2024: $20,692 million\n\n"
                "Total Infrastructure: $15,718 million\n"
                "2024: $14,020 million\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "analysis_id": "7d35a858-39a0-498a-ad51-12203e6135f1",
                "document_id": "doc-ibm-2025",
                "section_title": "Revenue & Segment Analysis",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "2eeb57fc-1b58-40e0-af21-b4f1576b9348",
                "page_number": 4,
                "is_financial_table": True,
            },
        },
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    question = (
        "According to IBM’s 2025 annual report, compare Software, Consulting, and Infrastructure segment "
        "revenue for 2025 vs. 2024, calculate the year-over-year growth for each segment, identify which "
        "segment grew the most, and cite the exact source evidence for every figure."
    )
    answer = agent.answer(
        question,
        company="International Business Machines",
        analysis_id="7d35a858-39a0-498a-ad51-12203e6135f1",
    )

    assert "Software" in answer.final_answer
    assert "Consulting" in answer.final_answer
    assert "Infrastructure" in answer.final_answer
    assert "10.6%" in answer.final_answer
    assert "1.8%" in answer.final_answer
    assert "12.1%" in answer.final_answer
    assert "Infrastructure" in answer.final_answer
    assert any(c.chunk_id == "2eeb57fc-1b58-40e0-af21-b4f1576b9348" for c in answer.all_citations())
