"""General-Purpose Financial Reasoning & Retrieval Test Suite.

Verifies that the Research Agent performs generalized financial reasoning without relying
on predefined question patterns or hardcoded branching:
1. Simple factual financial question
2. Multi-year comparative analysis with programmatic growth calculation
3. Causal 'why did X happen' reasoning (distinguishing management cause from inference)
4. 'Which year was best/worst and why' multi-period reasoning
5. Financial statement interpretation (Income Statement vs Balance Sheet vs Cash Flows)
6. Compound multi-part question decomposition
7. Insufficient evidence handling (explicit missing data statement)
8. Nuance disambiguation: realized/operating/impairment loss vs company-wide net loss
9. Programmatic calculations from grounded source figures only
10. Multi-section cross-referencing (Financial Statements + MD&A)
11. Management explanation vs unsupported claims
12. Completely unseen / arbitrarily phrased financial questions
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List, Optional
from research_agent import (
    ResearchAgent,
    QuestionIntentAnalyzer,
    DynamicRetrievalPlanner,
    QuestionIntentType,
    calculate_growth_rate,
    calculate_margin,
    parse_numeric_value,
    extract_tables_from_text,
)


class GeneralReasoningMockCollection:
    """Mock ChromaDB collection with multi-statement and multi-year financial filings."""

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

        # Match relevance based on query word overlap
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


@pytest.fixture
def multi_year_filing_collection():
    records = [
        {
            "id": "chunk-inc-01",
            "document": (
                "Consolidated Statement of Operations (In millions)\n\n"
                "Total Revenue: 2025: $65,400 | 2024: $58,200 | 2023: $50,500\n"
                "Cost of Revenue: 2025: $32,100 | 2024: $26,100 | 2023: $22,000\n"
                "Gross Profit: 2025: $33,300 | 2024: $32,100 | 2023: $28,500\n"
                "Operating Expenses (SG&A and R&D): 2025: $24,800 | 2024: $18,200 | 2023: $15,100\n"
                "Operating Income: 2025: $8,500 | 2024: $13,900 | 2023: $13,400\n"
                "Net Income: 2025: $6,200 | 2024: $11,100 | 2023: $10,200\n"
                "Diluted Earnings Per Share: 2025: $6.80 | 2024: $12.10 | 2023: $11.05\n"
            ),
            "metadata": {
                "company_name": "Apex Global Technologies",
                "analysis_id": "apex-session",
                "document_id": "apex-doc-2025",
                "section_title": "Income Statement",
                "source_file": "apex_2025_annual_report.pdf",
                "chunk_id": "chunk-inc-01",
                "is_financial_table": True,
            },
        },
        {
            "id": "chunk-mda-01",
            "document": (
                "Management Discussion and Analysis — Operating Results and Cost Drivers\n\n"
                "Although revenue expanded 12.4% in 2025 driven by cloud customer expansion, "
                "operating income and net income declined significantly compared to 2024. "
                "Management attributed the margin deterioration primarily to accelerated investments in AI infrastructure "
                "and higher integration costs related to the recent enterprise cloud acquisition. "
                "Higher R&D payroll and SG&A restructuring costs represented $6.6 billion of additional operating expenses."
            ),
            "metadata": {
                "company_name": "Apex Global Technologies",
                "analysis_id": "apex-session",
                "document_id": "apex-doc-2025",
                "section_title": "Management Discussion and Analysis",
                "source_file": "apex_2025_annual_report.pdf",
                "chunk_id": "chunk-mda-01",
            },
        },
        {
            "id": "chunk-bal-01",
            "document": (
                "Consolidated Balance Sheets (In millions)\n\n"
                "Cash and cash equivalents: 2025: $14,200 | 2024: $18,500\n"
                "Total Debt: 2025: $42,500 | 2024: $31,000\n"
                "Total Stockholders' Equity: 2025: $28,900 | 2024: $30,400\n"
                "Total Liabilities: 2025: $68,200 | 2024: $52,100\n"
            ),
            "metadata": {
                "company_name": "Apex Global Technologies",
                "analysis_id": "apex-session",
                "document_id": "apex-doc-2025",
                "section_title": "Balance Sheet",
                "source_file": "apex_2025_annual_report.pdf",
                "chunk_id": "chunk-bal-01",
                "is_financial_table": True,
            },
        },
        {
            "id": "chunk-notes-01",
            "document": (
                "Note 14. Realized and Unrealized Loss on Marketable Securities\n\n"
                "During 2025, the company recorded a realized loss of $68 million on the disposition of legacy debt securities. "
                "This other non-operating loss is recorded within other expense and does not represent an operating or net business loss."
            ),
            "metadata": {
                "company_name": "Apex Global Technologies",
                "analysis_id": "apex-session",
                "document_id": "apex-doc-2025",
                "section_title": "Notes to the Financial Statements",
                "source_file": "apex_2025_annual_report.pdf",
                "chunk_id": "chunk-notes-01",
            },
        },
    ]
    return GeneralReasoningMockCollection(records)


# 1. Simple factual financial query
def test_simple_factual_query(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("What was the diluted EPS for Apex Global Technologies in 2025?", company="Apex Global Technologies")
    assert "$6.80" in answer.final_answer or "6.80" in answer.final_answer
    assert any(c.chunk_id == "chunk-inc-01" for c in answer.all_citations())


# 2. Multi-year comparison & dynamic table formatting with growth calculation
def test_multi_year_comparison_and_table_synthesis(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("Compare revenue, gross profit and operating income between 2025 and 2024.", company="Apex Global Technologies")
    assert len(answer.all_citations()) > 0
    # Must synthesize numbers from filing
    assert "65,400" in answer.final_answer or "58,200" in answer.final_answer or "8,500" in answer.final_answer


# 3. Causal 'why did X happen' reasoning
def test_causal_reasoning_why_profit_declined_despite_revenue_growth(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    question = "Why did operating profit decline in 2025 despite revenue increasing?"
    answer = agent.answer(question, company="Apex Global Technologies")

    # Verify retrieval included MD&A
    citations = answer.all_citations()
    assert any(c.chunk_id == "chunk-mda-01" for c in citations)
    # Verify answer explains the cause (AI infrastructure, integration costs, or SG&A/R&D increase)
    answer_text = answer.final_answer.lower()
    assert any(term in answer_text for term in ["ai infrastructure", "acquisition", "operating expenses", "investment", "r&d", "sg&a", "cost"])


# 4. 'Which year was best/worst and why' multi-period reasoning
def test_which_year_was_strongest_profitability(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("Which year had the highest operating income and net income?", company="Apex Global Technologies")
    assert "2024" in answer.final_answer or "13,900" in answer.final_answer
    assert any(c.chunk_id == "chunk-inc-01" for c in answer.all_citations())


# 5. Financial statement interpretation (Income Statement vs Balance Sheet vs Cash Flows)
def test_financial_statement_debt_interpretation(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("What happened to total debt and stockholders equity on the balance sheet?", company="Apex Global Technologies")
    assert "$42,500" in answer.final_answer or "42,500" in answer.final_answer or "31,000" in answer.final_answer
    assert any(c.chunk_id == "chunk-bal-01" for c in answer.all_citations())


# 6. Compound multi-part question decomposition
def test_compound_multi_part_question(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("What was the 2025 revenue? And what was total debt on the balance sheet?", company="Apex Global Technologies")
    assert len(answer.steps) >= 2
    assert any(c.chunk_id == "chunk-inc-01" for c in answer.all_citations())
    assert any(c.chunk_id == "chunk-bal-01" for c in answer.all_citations())


# 7. Insufficient evidence handling (explicit missing data statement)
def test_insufficient_evidence_handling_explicit():
    empty_col = GeneralReasoningMockCollection([])
    agent = ResearchAgent(empty_col)
    answer = agent.answer("What was the company's patent litigation reserve in 2021?", company="Apex Global Technologies")
    assert "insufficient" in answer.final_answer.lower() or "no indexed document evidence was found" in answer.final_answer.lower()
    assert len(answer.all_citations()) == 0


# 8. Nuance disambiguation: realized/operating/impairment loss vs company-wide net loss
def test_disambiguate_component_realized_loss_from_net_loss(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("Did the company record a net loss in 2025 or what loss occurred?", company="Apex Global Technologies")
    assert any(c.chunk_id in ["chunk-inc-01", "chunk-notes-01"] for c in answer.all_citations())
    # Net income was positive $6,200M, while realized loss was $68M
    assert "68" in answer.final_answer or "6,200" in answer.final_answer or "realized loss" in answer.final_answer.lower()


# 9. Programmatic calculations (growth rate, margins)
def test_programmatic_calculation_helpers():
    # Test growth rate calculation
    growth = calculate_growth_rate(65400, 58200)
    assert growth is not None
    assert round(growth, 1) == 12.4

    # Test margin calculation
    margin = calculate_margin(8500, 65400)
    assert margin is not None
    assert round(margin, 1) == 13.0

    # Test negative parentheses parsing
    val = parse_numeric_value("(95.4)")
    assert val == -95.4


# 10. Multi-section cross-referencing (Financial Statements + MD&A)
def test_multi_section_cross_referencing(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("What were the operating results and what cost factors did management discuss?", company="Apex Global Technologies")
    citations = answer.all_citations()
    sections = {c.section for c in citations}
    assert "Income Statement" in sections or "Management Discussion and Analysis" in sections


# 11. Management explanation vs unsupported claims
def test_management_explanation_extraction(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    answer = agent.answer("How did management explain the increased operating expenses in 2025?", company="Apex Global Technologies")
    assert any(c.chunk_id == "chunk-mda-01" for c in answer.all_citations())
    assert "ai infrastructure" in answer.final_answer.lower() or "acquisition" in answer.final_answer.lower() or "r&d" in answer.final_answer.lower()


# 12. Completely unseen / arbitrarily phrased financial questions
def test_unseen_arbitrary_question_reasoning(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    # Question with unprecedented phrasing
    unseen_q = "Trace the trajectory of top-line growth against bottom-line contraction for Apex Global Technologies."
    answer = agent.answer(unseen_q, company="Apex Global Technologies")

    assert answer.steps
    assert len(answer.all_citations()) > 0
    # Must retrieve relevant financial data
    assert any(c.chunk_id in ["chunk-inc-01", "chunk-mda-01"] for c in answer.all_citations())
    assert len(answer.final_answer) > 20


# 13. Noise Rejection & TOC Filtering
def test_table_of_contents_noise_filtering():
    records = [
        {
            "id": "chunk-toc",
            "document": "Table of Contents\nItem 1. Business .... Page 4\nItem 7. MD&A .... Page 28\nItem 8. Financial Statements .... Page 45",
            "metadata": {
                "company_name": "Apex Global Technologies",
                "section_title": "Table of Contents",
                "chunk_id": "chunk-toc",
            }
        },
        {
            "id": "chunk-data",
            "document": "Total Revenue for 2025 was $65,400 million compared to $58,200 million in 2024.",
            "metadata": {
                "company_name": "Apex Global Technologies",
                "section_title": "Income Statement",
                "chunk_id": "chunk-data",
            }
        }
    ]
    col = GeneralReasoningMockCollection(records)
    agent = ResearchAgent(col)
    answer = agent.answer("What was the 2025 revenue for Apex Global Technologies?", company="Apex Global Technologies")
    assert any(c.chunk_id == "chunk-data" for c in answer.all_citations())
    assert not any(c.chunk_id == "chunk-toc" for c in answer.all_citations())


# 14. Multi-part sub-question structured output
def test_multi_part_sub_questions_structured_output(multi_year_filing_collection):
    agent = ResearchAgent(multi_year_filing_collection)
    q = "What was the 2025 revenue? And what was total debt on the balance sheet?"
    answer = agent.answer(q, company="Apex Global Technologies")
    assert "#### 1." in answer.final_answer or "65,400" in answer.final_answer
    assert "#### 2." in answer.final_answer or "42,500" in answer.final_answer

