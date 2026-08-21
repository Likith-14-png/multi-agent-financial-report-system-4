"""Regression test suite for analytical financial research reasoning and relevance filtering.

Covers:
1. Operating-margin causal inquiry (rejects balance sheet liabilities/cash flow)
2. Largest-impact / primary driver ranking
3. Multi-year financial comparison & calculations
4. Multi-part financial research inquiries
5. Insufficient-evidence handling (exact contract phrase)
6. Rejection of irrelevant Balance Sheet, Cash Flow, and TOC chunks
7. Prevention of unsupported causal/impact claims
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List, Optional
from research_agent import ResearchAgent


class AnalyticalMockCollection:
    """Mock ChromaDB collection with financial statements, MD&A, and irrelevant noise chunks."""

    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def query(self, query_texts: List[str], n_results: int = 4, where: Optional[Dict[str, Any]] = None):
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


@pytest.fixture
def ibm_analytical_collection():
    records = [
        {
            "id": "ibm-mda-margin",
            "document": (
                "Management Discussion and Analysis — Operating Profitability & Margin Dynamics\n\n"
                "Operating margin expanded by 140 basis points year-over-year to 16.8% in 2025. "
                "The primary driver of margin expansion was a favorable portfolio mix shift toward higher-margin hybrid cloud and AI software, "
                "which grew 10.6% during the fiscal year. "
                "Additionally, continuous workforce productivity initiatives and operational restructuring delivered $1.2 billion in structural cost savings, "
                "partially offset by targeted investments in enterprise AI infrastructure and Go-To-Market expansion."
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "section_title": "Management Discussion and Analysis",
                "source_file": "ibm_2025_annual_report.pdf",
                "chunk_id": "ibm-mda-margin",
                "report_year": 2025,
            },
        },
        {
            "id": "ibm-inc-statement",
            "document": (
                "Consolidated Statement of Operations (In millions)\n\n"
                "Total Revenue: 2025: $62,750 | 2024: $61,860\n"
                "Total Operating Expenses: 2025: $52,208 | 2024: $52,333\n"
                "Operating Income: 2025: $10,542 | 2024: $9,527\n"
                "Operating Margin: 2025: 16.8% | 2024: 15.4%\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "section_title": "Income Statement",
                "source_file": "ibm_2025_annual_report.pdf",
                "chunk_id": "ibm-inc-statement",
                "report_year": 2025,
                "is_financial_table": True,
            },
        },
        {
            "id": "ibm-bal-liabilities",
            "document": (
                "Consolidated Balance Sheets (In millions)\n\n"
                "Total Liabilities: 2025: $109,783 | 2024: $103,420\n"
                "Total Debt: 2025: $51,800 | 2024: $48,200\n"
                "Post-retirement benefit obligations: 2025: $12,400 | 2024: $13,100\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "section_title": "Balance Sheet",
                "source_file": "ibm_2025_annual_report.pdf",
                "chunk_id": "ibm-bal-liabilities",
                "report_year": 2025,
                "is_financial_table": True,
            },
        },
        {
            "id": "ibm-toc-noise",
            "document": (
                "Table of Contents\n"
                "Item 1. Business .................... Page 4\n"
                "Item 7. MD&A ....................... Page 28\n"
                "Item 8. Financial Statements ......... Page 65\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "section_title": "Table of Contents",
                "source_file": "ibm_2025_annual_report.pdf",
                "chunk_id": "ibm-toc-noise",
            },
        },
    ]
    return AnalyticalMockCollection(records)


# 1. Operating-margin causal question & largest impact
def test_operating_margin_reasons_and_largest_impact(ibm_analytical_collection):
    agent = ResearchAgent(ibm_analytical_collection)
    question = "What were the key reasons for changes in IBM's operating margin, and which factors had the largest impact?"
    answer = agent.answer(question, company="International Business Machines")

    # Verify structured analytical response
    assert "### Answer" in answer.final_answer
    assert "### Key Evidence" in answer.final_answer
    assert "### Main Factors" in answer.final_answer
    assert "### Largest Impact" in answer.final_answer
    assert "### Source Citations" in answer.final_answer

    # Verify relevant MD&A evidence was retrieved and cited
    citations = answer.all_citations()
    assert any(c.chunk_id == "ibm-mda-margin" for c in citations)

    # Verify irrelevant Balance Sheet liabilities and TOC were NOT cited
    assert not any(c.chunk_id == "ibm-bal-liabilities" for c in citations)
    assert not any(c.chunk_id == "ibm-toc-noise" for c in citations)

    # Verify factors and largest impact are explained
    ans_low = answer.final_answer.lower()
    assert "software" in ans_low or "mix shift" in ans_low or "productivity" in ans_low
    assert "16.8%" in answer.final_answer or "140 basis points" in ans_low or "expansion" in ans_low


# 2. Rejection of irrelevant Balance Sheet / TOC chunks
def test_rejection_of_irrelevant_chunks(ibm_analytical_collection):
    agent = ResearchAgent(ibm_analytical_collection)
    question = "Explain the drivers of operating profitability and margin changes for IBM."
    answer = agent.answer(question, company="International Business Machines")

    # Assert no balance sheet liabilities or TOC text in answer
    assert "Total Liabilities" not in answer.final_answer
    assert "Post-retirement benefit" not in answer.final_answer
    assert "Table of Contents" not in answer.final_answer
    assert "Item 1." not in answer.final_answer


# 3. Insufficient evidence handling
def test_insufficient_grounded_evidence_contract():
    empty_col = AnalyticalMockCollection([])
    agent = ResearchAgent(empty_col)
    question = "What caused the change in carbon emission credit provisions for Acme Corp in 2019?"
    answer = agent.answer(question, company="Acme Corp")

    assert "Insufficient grounded evidence was retrieved to answer this question reliably." in answer.final_answer
    assert len(answer.all_citations()) == 0


# 4. Multi-year comparison & calculation
def test_multi_year_comparison_reasoning(ibm_analytical_collection):
    agent = ResearchAgent(ibm_analytical_collection)
    question = "Compare revenue, operating expenses and operating income between 2025 and 2024 for IBM."
    answer = agent.answer(question, company="International Business Machines")

    assert "62,750" in answer.final_answer or "61,860" in answer.final_answer or "10,542" in answer.final_answer
    assert any(c.chunk_id == "ibm-inc-statement" for c in answer.all_citations())


# 5. Multi-part financial inquiry with distinct sub-answers
def test_multi_part_financial_inquiry(ibm_analytical_collection):
    agent = ResearchAgent(ibm_analytical_collection)
    question = "What was the 2025 revenue? And what was total debt on the balance sheet?"
    answer = agent.answer(question, company="International Business Machines")

    assert len(answer.steps) >= 2
    assert any(c.chunk_id == "ibm-inc-statement" for c in answer.all_citations())
    assert any(c.chunk_id == "ibm-bal-liabilities" for c in answer.all_citations())


# 6. Claim-level citations mapping
def test_claim_level_citations_populated(ibm_analytical_collection):
    agent = ResearchAgent(ibm_analytical_collection)
    question = "What were the key reasons for changes in IBM's operating margin, and which factors had the largest impact?"
    answer = agent.answer(question, company="International Business Machines")

    assert answer.evidence_claims
    for ec in answer.evidence_claims:
        assert "chunk_id" in ec
        assert "section" in ec
        assert "company" in ec
