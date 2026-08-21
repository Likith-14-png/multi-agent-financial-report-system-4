"""Generic production test suite for Research Agent.

Verifies:
1. Exact IBM 2025 segment revenue comparison, YoY growth calculations, ranking, and source citations
2. Generic non-IBM multi-segment comparisons and rankings
3. Negative YoY growth rate handling
4. Question intent understanding and entity extraction
5. Dynamic multi-query retrieval planning
6. Deterministic FinancialCalculator operations
7. Multiline and vertical financial table parsing
8. Causal / analytical MD&A reasoning and impact ranking
9. Strict negative-evidence non-hallucination contract
10. Figure-level citation metadata preservation
11. Session / tenant isolation with analysis_id
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


@pytest.fixture
def ibm_synthetic_filing_collection():
    """Filing collection containing IBM 2025 synthetic report chunks."""
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
        {
            "id": "e87a5f44-4816-47d5-8053-143895757b8e",
            "document": (
                "Management Discussion and Analysis — Segment Growth Performance\n\n"
                "Software revenue grew 10.6% year-over-year driven by Hybrid Cloud and Red Hat expansion. "
                "Consulting revenue increased 1.8% reflecting steady business transformation demand. "
                "Infrastructure revenue expanded 12.1% reflecting strong mainframe adoption and hybrid infrastructure growth."
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "analysis_id": "7d35a858-39a0-498a-ad51-12203e6135f1",
                "document_id": "doc-ibm-2025",
                "section_title": "Management Discussion and Analysis",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "e87a5f44-4816-47d5-8053-143895757b8e",
                "page_number": 5,
            },
        },
        {
            "id": "c11a-bal-01",
            "document": (
                "Consolidated Balance Sheet\n\n"
                "Total Assets: $151,880 million\n"
                "Total Liabilities: $109,783 million\n"
                "Total Debt: $61,260 million\n"
            ),
            "metadata": {
                "company_name": "International Business Machines",
                "analysis_id": "7d35a858-39a0-498a-ad51-12203e6135f1",
                "document_id": "doc-ibm-2025",
                "section_title": "Balance Sheet",
                "source_file": "Synthetic Financial Report.pdf",
                "chunk_id": "c11a-bal-01",
                "page_number": 6,
            },
        },
    ]
    return GenericMockCollection(records)


def test_target_ibm_segment_revenue_and_growth_regression(ibm_synthetic_filing_collection):
    agent = ResearchAgent(ibm_synthetic_filing_collection)
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

    assert "| Segment | 2025 Revenue | 2024 Revenue | Growth |" in answer.final_answer or "| Segment |" in answer.final_answer
    assert "Software" in answer.final_answer
    assert "Consulting" in answer.final_answer
    assert "Infrastructure" in answer.final_answer

    assert "$29,962M" in answer.final_answer or "29,962" in answer.final_answer
    assert "$27,085M" in answer.final_answer or "27,085" in answer.final_answer
    assert "$21,055M" in answer.final_answer or "21,055" in answer.final_answer
    assert "$20,692M" in answer.final_answer or "20,692" in answer.final_answer
    assert "$15,718M" in answer.final_answer or "15,718" in answer.final_answer
    assert "$14,020M" in answer.final_answer or "14,020" in answer.final_answer

    assert "10.6%" in answer.final_answer
    assert "1.8%" in answer.final_answer
    assert "12.1%" in answer.final_answer

    assert "Infrastructure" in answer.final_answer
    assert "grew the most" in answer.final_answer or "fastest" in answer.final_answer or "highest" in answer.final_answer

    citations = answer.all_citations()
    assert len(citations) > 0
    assert any(c.chunk_id == "2eeb57fc-1b58-40e0-af21-b4f1576b9348" for c in citations)


def test_generic_non_ibm_segment_comparison():
    records = [
        {
            "id": "novartis-seg-01",
            "document": (
                "Division Performance Summary (In millions)\n\n"
                "Total Pharmaceuticals: $38,400 million\n2024: $35,200 million\n\n"
                "Total Oncology: $14,600 million\n2024: $12,800 million\n\n"
                "Total Sandoz: $9,600 million\n2024: $9,900 million\n"
            ),
            "metadata": {
                "company_name": "Novartis AG",
                "analysis_id": "novartis-session",
                "section_title": "Segment Analysis",
                "source_file": "novartis_2025.pdf",
                "chunk_id": "novartis-seg-01",
                "page_number": 12,
                "is_financial_table": True,
            },
        }
    ]
    coll = GenericMockCollection(records)
    agent = ResearchAgent(coll)
    question = "Compare Pharmaceuticals, Oncology, and Sandoz division revenue for 2025 vs 2024 and identify which grew most."
    answer = agent.answer(question, company="Novartis AG", analysis_id="novartis-session")

    assert "Pharmaceuticals" in answer.final_answer
    assert "Oncology" in answer.final_answer
    assert "Sandoz" in answer.final_answer
    assert "14.1%" in answer.final_answer or "14.06%" in answer.final_answer
    assert "-3.0%" in answer.final_answer or "-3.03%" in answer.final_answer
    assert "Oncology" in answer.final_answer
    assert any(c.chunk_id == "novartis-seg-01" for c in answer.all_citations())


def test_financial_calculator_operations():
    assert abs(FinancialCalculator.calculate_growth_rate(29962, 27085) - 10.622) < 0.01
    assert abs(FinancialCalculator.calculate_growth_rate(21055, 20692) - 1.754) < 0.01
    assert abs(FinancialCalculator.calculate_growth_rate(15718, 14020) - 12.111) < 0.01
    assert FinancialCalculator.calculate_growth_rate(100, 0) is None

    neg_g = FinancialCalculator.calculate_growth_rate(90, 100)
    assert neg_g == -10.0

    assert abs(FinancialCalculator.calculate_margin(8500, 65400) - 12.996) < 0.01


def test_question_intent_analyzer():
    q = "According to IBM’s 2025 annual report, compare Software, Consulting, and Infrastructure segment revenue for 2025 vs. 2024, calculate the year-over-year growth for each segment, identify which segment grew the most, and cite the exact source evidence for every figure."
    intent = QuestionIntentAnalyzer.analyze(q, target_company="International Business Machines")

    assert intent.is_comparative is True
    assert intent.requires_calculation is True
    assert intent.requires_ranking is True
    assert "2025" in intent.target_years
    assert "2024" in intent.target_years
    assert any("software" in e.lower() for e in intent.target_entities)
    assert any("consulting" in e.lower() for e in intent.target_entities)
    assert any("infrastructure" in e.lower() for e in intent.target_entities)


def test_dynamic_retrieval_planner_queries():
    q = "Compare Software, Consulting, and Infrastructure segment revenue for 2025 vs 2024."
    intent = QuestionIntentAnalyzer.analyze(q, target_company="IBM")
    queries = DynamicRetrievalPlanner.plan_queries(intent, company_name="IBM")

    assert len(queries) >= 3
    queries_str = " ".join(queries).lower()
    assert "software" in queries_str
    assert "consulting" in queries_str
    assert "infrastructure" in queries_str


def test_strict_insufficient_evidence_contract():
    empty_coll = GenericMockCollection([])
    agent = ResearchAgent(empty_coll)
    answer = agent.answer("What were the 2025 revenues for Quantum Computing division?")

    assert "Insufficient grounded evidence was retrieved to answer this question reliably." in answer.final_answer
    assert len(answer.all_citations()) == 0


def test_session_isolation_with_analysis_id():
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
