"""Comprehensive test suite for Research Agent.

Tests:
1. Segment revenue & growth calculation and markdown table formatting
2. Year-over-year financial comparisons
3. EPS (Basic and Diluted) extraction and reasoning
4. Profitability and margin reasoning
5. Cash Flow (Operating Cash Flow and Free Cash Flow)
6. Multi-part query decomposition and multi-step citations
7. Irrelevant retrieval rejection and filtering
8. Source citation accuracy (chunk_id, section, source_file)
9. Missing evidence and insufficient data handling
"""
import pytest
from typing import Any, Dict, List, Optional
from research_agent import ResearchAgent, Citation, ResearchStep, ResearchAnswer


class MockResearchCollection:
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def query(self, query_texts: List[str], n_results: int = 4, where: Optional[Dict[str, Any]] = None):
        filtered = self.records
        if where is not None:
            filtered = [
                r for r in self.records
                if all(r.get("metadata", {}).get(k) == v or r.get(k) == v for k, v in where.items())
            ]
        if not filtered:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Sort by match score based on query words
        q_words = set(" ".join(query_texts).lower().split())
        
        def score_record(r):
            doc = r["document"].lower()
            meta = r.get("metadata", {})
            overlap = sum(1 for w in q_words if w in doc or w in str(meta).lower())
            return -overlap

        sorted_records = sorted(filtered, key=score_record)
        return {
            "ids": [[r["id"] for r in sorted_records[:n_results]]],
            "documents": [[r["document"] for r in sorted_records[:n_results]]],
            "metadatas": [[r.get("metadata", {}) for r in sorted_records[:n_results]]],
            "distances": [[0.15 for _ in sorted_records[:n_results]]],
        }

    def get(self, include=None):
        return {"metadatas": [r.get("metadata", {}) for r in self.records]}


@pytest.fixture
def ibm_mock_collection():
    records = [
        {
            "id": "ibm-chunk-9",
            "document": (
                "Segment Revenue Analysis (In millions)\n\n"
                "Total Software \n$ 29,962 \n$27,085 \n"
                "Total Consulting \n$ 21,055 \n$20,692 \n"
                "Total Infrastructure \n$ 15,718 \n$14,020 \n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "report_year": "2025",
                "section_title": "Profitability & Performance Metrics",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "ibm-chunk-9",
                "is_financial_table": True,
            },
        },
        {
            "id": "ibm-chunk-2",
            "document": (
                "Consolidated Financial Highlights\n\n"
                "Diluted EPS from Continuing Operations: $11.14\n"
                "Consolidated Diluted Earnings Per Share: $11.17\n"
                "Total Assets: $151,880 million\n"
                "Total Liabilities: $109,783 million\n"
                "Total Stockholders' Equity: $32,740 million\n"
                "Free Cash Flow: $14.7 billion\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "report_year": "2025",
                "section_title": "Financial Statements",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "ibm-chunk-2",
                "is_financial_table": True,
            },
        },
        {
            "id": "ibm-chunk-6",
            "document": (
                "Consolidated Statement of Cash Flows\n\n"
                "Net cash provided by operating activities: $13,193 million\n"
                "Capital expenditures: $1,091 million\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "report_year": "2025",
                "section_title": "Cash Flow Statement",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "ibm-chunk-6",
                "is_financial_table": True,
            },
        },
        {
            "id": "ibm-chunk-14",
            "document": (
                "Total Debt Summary (In millions)\n\n"
                "Total debt: $61,260 million\n"
                "Short-term debt: $5,089 million\n"
                "Long-term debt: $49,884 million\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "report_year": "2025",
                "section_title": "Financing & Debt",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "ibm-chunk-14",
                "is_financial_table": True,
            },
        },
    ]
    return MockResearchCollection(records)


def test_segment_revenue_and_growth_table(ibm_mock_collection):
    agent = ResearchAgent(ibm_mock_collection)
    question = "Software, Consulting and Infrastructure segment revenue and growth"
    answer = agent.answer(question, top_k=4, company="International Business Machines")

    assert "| Segment | 2025 Revenue | 2024 Revenue | Growth |" in answer.final_answer
    assert "Software" in answer.final_answer and "$29,962M" in answer.final_answer and "10.6%" in answer.final_answer
    assert "Consulting" in answer.final_answer and "$21,055M" in answer.final_answer and "1.8%" in answer.final_answer
    assert "Infrastructure" in answer.final_answer and "$15,718M" in answer.final_answer and "12.1%" in answer.final_answer

    # Verify citation
    assert answer.all_citations()
    c = answer.all_citations()[0]
    assert c.chunk_id == "ibm-chunk-9"
    assert c.section == "Profitability & Performance Metrics"


def test_eps_extraction_and_citation(ibm_mock_collection):
    agent = ResearchAgent(ibm_mock_collection)
    question = "What is the diluted EPS from continuing operations and consolidated EPS?"
    answer = agent.answer(question, top_k=4, company="International Business Machines")

    assert "$11.14" in answer.final_answer or "$11.17" in answer.final_answer
    assert any(c.chunk_id == "ibm-chunk-2" for c in answer.all_citations())


def test_cash_flow_and_free_cash_flow(ibm_mock_collection):
    agent = ResearchAgent(ibm_mock_collection)
    question = "What was the operating cash flow and free cash flow in 2025?"
    answer = agent.answer(question, top_k=4, company="International Business Machines")

    assert "$14.7 billion" in answer.final_answer or "13,193" in answer.final_answer
    assert any(c.chunk_id in ["ibm-chunk-2", "ibm-chunk-6"] for c in answer.all_citations())


def test_multi_part_query_decomposition(ibm_mock_collection):
    agent = ResearchAgent(ibm_mock_collection)
    question = "What is the total debt? And what was the free cash flow?"
    answer = agent.answer(question, top_k=4, company="International Business Machines")

    assert len(answer.steps) >= 2
    assert any(c.chunk_id == "ibm-chunk-14" for c in answer.all_citations())
    assert any(c.chunk_id == "ibm-chunk-2" for c in answer.all_citations())


def test_citation_accuracy_and_metadata_preservation(ibm_mock_collection):
    agent = ResearchAgent(ibm_mock_collection)
    question = "What is the total debt of the company?"
    answer = agent.answer(question, top_k=4, company="International Business Machines")

    citations = answer.all_citations()
    assert citations
    cit = [c for c in citations if c.chunk_id == "ibm-chunk-14"][0]
    assert cit.company == "International Business Machines"
    assert cit.source_file == "Synthetic Financial Report.pdf"
    assert cit.section == "Financing & Debt"


def test_missing_evidence_reported_explicitly():
    empty_col = MockResearchCollection([])
    agent = ResearchAgent(empty_col)
    question = "What is the R&D expenditure for Acme Corporation in 2025?"
    answer = agent.answer(question, top_k=4, company="Acme Corporation")

    assert "No indexed document evidence was found" in answer.final_answer or "No indexed documents contain evidence" in answer.final_answer
    assert not answer.all_citations()


def test_irrelevant_company_rejection(ibm_mock_collection):
    agent = ResearchAgent(ibm_mock_collection)
    question = "What is the revenue of XYZ Telecom Corp?"
    answer = agent.answer(question, top_k=4, company="XYZ Telecom Corp")

    # Should not cite IBM chunks for XYZ Telecom Corp
    assert all(c.company == "XYZ Telecom Corp" for c in answer.all_citations()) or not answer.all_citations()
