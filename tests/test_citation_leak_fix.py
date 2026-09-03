"""Closed-loop integration tests for citation leak prevention, evidence-metric synchronization,
metric extraction guardrails, and explanation remediation in the Research Agent.
"""
from typing import Any, Dict, List
import pytest

from research_agent import (
    Citation,
    ResearchAgent,
    clean_citation_references,
)


class MockCollection:
    """Mock ChromaDB collection for isolated integration testing."""
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def query(self, query_texts, n_results=4, where=None):
        matched = self.records
        if where:
            def matches(meta, conds):
                for k, v in conds.items():
                    if k == "$or":
                        if not any(matches(meta, sub) for sub in v):
                            return False
                    elif k == "$and":
                        if not all(matches(meta, sub) for sub in v):
                            return False
                    elif meta.get(k) != v:
                        return False
                return True
            matched = [r for r in matched if matches(r["metadata"], where)]
        limit = min(n_results, len(matched))
        return {
            "ids": [[r["id"] for r in matched[:limit]]],
            "documents": [[r["document"] for r in matched[:limit]]],
            "metadatas": [[r["metadata"] for r in matched[:limit]]],
            "distances": [[0.05 for _ in matched[:limit]]],
        }

    def get(self, include=None):
        return {"metadatas": [r["metadata"] for r in self.records]}


def _make_record(chunk_id: str, document: str, section: str, page: str = "1", year: str = "2026", company: str = "Amagi") -> Dict[str, Any]:
    return {
        "id": chunk_id,
        "document": document,
        "metadata": {
            "company_name": company,
            "section_title": section,
            "source_file": "Amagi.pdf",
            "chunk_id": chunk_id,
            "page_number": page,
            "report_year": year,
        },
    }


def test_clean_citation_references_utility():
    """Verify clean_citation_references parses raw metadata and eliminates UUIDs."""
    raw_leaked = (
        "For FY26, Amagi's total Adjusted EBITDA was ₹155.7 crore, and the reported Adjusted EBITDA Margin was 10.3% "
        "[[Stock Tickers | Annual Report | 2026 | Cover & Company Information | Amagi.pdf | Page 1-6 | chunk 46be925e-fdde-4e37-8c90-3f27ad81b221], "
        "[Stock Tickers | Annual Report | 2026 | Financial Charts Data | Amagi.pdf | Page 17-21 | chunk 94936eef-6032-48ca-aeb6-eb32036ef51b], "
        "[Stock Tickers | Annual Report | 2026 | Consolidated Financial Data & | Amagi.pdf | Page 21-22 | chunk 91be1697-9e27-4da3-ba7e-1b0cb3f93632]]."
    )

    cleaned = clean_citation_references(raw_leaked, preferred_company="Amagi")

    # Assertions
    assert "46be925e" not in cleaned
    assert "94936eef" not in cleaned
    assert "91be1697" not in cleaned
    assert "chunk" not in cleaned.lower()
    assert "[[" not in cleaned
    assert "]]" not in cleaned
    assert "Stock Tickers" not in cleaned
    assert "[Amagi FY26, Page 1-6]" in cleaned
    assert "[Amagi FY26, Page 17-21]" in cleaned
    assert "[Amagi FY26, Page 21-22]" in cleaned


def test_citation_to_clean_citation():
    """Verify Citation.to_clean_citation produces [Document Name, Page X]."""
    cit = Citation(
        company="Stock Tickers",
        doc_type="Annual Report",
        section="Consolidated Financial Data",
        source_file="Amagi.pdf",
        chunk_id="91be1697-9e27-4da3-ba7e-1b0cb3f93632",
        snippet="Adjusted EBITDA was ₹155.7 crore.",
        page="21-22",
        report_year=2026,
    )

    clean_str = cit.to_clean_citation(preferred_company="Amagi")
    assert clean_str == "[Amagi FY26, Page 21-22]"

    # Test fallback when no preferred company provided (inferred from Amagi.pdf)
    clean_fallback = cit.to_clean_citation()
    assert clean_fallback == "[Amagi FY26, Page 21-22]"

    # Test to_dict includes clean citation and source_doc
    d = cit.to_dict()
    assert d["clean_citation"] == "[Amagi FY26, Page 21-22]"
    assert d["source_doc"] == "Amagi.pdf"
    assert d["pages"] == "21-22"
    assert d["chunk_id"] == "91be1697-9e27-4da3-ba7e-1b0cb3f93632"


def test_amagi_fy26_adjusted_ebitda_pipeline():
    """Closed-loop integration test reproducing Amagi FY26 EBITDA query.
    
    Verifies all 4 user symptoms:
    1. Chunk string leaks are stripped from final UI payload.
    2. Key Evidence attaches EBITDA tables, NOT unrelated ESG/permits data.
    3. Relevant Financial Metrics reflects ₹155.7 crore and 10.3%, suppressing generic error.
    4. Explanation provides analytical context distinct from Direct Answer.
    """
    ebitda_chunk = _make_record(
        chunk_id="91be1697-9e27-4da3-ba7e-1b0cb3f93632",
        document=(
            "Consolidated Financial Highlights FY26:\n"
            "Adjusted EBITDA for FY26 was ₹155.7 crore compared to ₹128.4 crore in FY25.\n"
            "The reported Adjusted EBITDA Margin was 10.3% against 9.1% in the previous year.\n"
            "Operating revenue grew 21% driven by cloud expansions."
        ),
        section="Consolidated Financial Highlights",
        page="21-22",
        year="2026",
        company="Amagi",
    )

    esg_noise_chunk = _make_record(
        chunk_id="esg-46be925e-noise-chunk",
        document=(
            "conformance after CAP Environmental permits and reporting 96.1% 96.9% "
            "Hazardous substances 97.6% 97.6% Solid waste 97.6% 97.6% Air emissions 97.6% 95.3% "
            "Water management 97.6% 97.6% Energy consumption and greenhouse gases 85.8% 87.4% "
            "Resource efficiency 99.2% 99.2% Risk."
        ),
        section="ESG & Environmental Compliance",
        page="45",
        year="2026",
        company="Stock Tickers",
    )

    collection = MockCollection([ebitda_chunk, esg_noise_chunk])
    agent = ResearchAgent(collection)

    # Simulate LLM generating the exact leaked response
    leaked_llm_response = (
        "For FY26, Amagi's total Adjusted EBITDA was ₹155.7 crore, and the reported Adjusted EBITDA Margin was 10.3% "
        "[[Stock Tickers | Annual Report | 2026 | Cover & Company Information | Amagi.pdf | Page 1-6 | chunk 46be925e-fdde-4e37-8c90-3f27ad81b221], "
        "[Stock Tickers | Annual Report | 2026 | Financial Charts Data | Amagi.pdf | Page 17-21 | chunk 94936eef-6032-48ca-aeb6-eb32036ef51b], "
        "[Stock Tickers | Annual Report | 2026 | Consolidated Financial Data & | Amagi.pdf | Page 21-22 | chunk 91be1697-9e27-4da3-ba7e-1b0cb3f93632]]."
    )
    agent._llm_generate = lambda prompt: leaked_llm_response

    question = "What was the total Adjusted EBITDA for FY26, and what was the reported EBITDA margin?"
    answer = agent.answer(question, company="Amagi")
    res_dict = answer.to_dict(analysis_id="test-analysis-123")

    # ------------------------------------------------------------- #
    # Task 1: Citation & Chunk Leak Prevention Assertions
    # ------------------------------------------------------------- #
    final_ans = res_dict["final_answer"]
    assert "46be925e" not in final_ans
    assert "94936eef" not in final_ans
    assert "91be1697" not in final_ans
    assert "chunk" not in final_ans.lower()
    assert "[[" not in final_ans
    assert "]]" not in final_ans
    assert "Stock Tickers" not in final_ans

    # Check that sources metadata array has clean citations and source_doc
    assert len(res_dict["sources"]) > 0
    first_src = res_dict["sources"][0]
    assert "source_doc" in first_src
    assert first_src["source_doc"] == "Amagi.pdf"
    assert "clean_citation" in first_src

    # ------------------------------------------------------------- #
    # Task 2: Evidence & Metric Synchronization Assertions
    # ------------------------------------------------------------- #
    # Key Evidence must contain EBITDA figures, NOT ESG/permits/hazardous substances
    assert "### Key Evidence" in final_ans
    key_evidence_part = final_ans.split("### Key Evidence")[1].split("###")[0]
    assert "155.7" in key_evidence_part or "10.3%" in key_evidence_part or "Adjusted EBITDA" in key_evidence_part
    assert "Hazardous substances" not in key_evidence_part
    assert "Environmental permits" not in key_evidence_part
    assert "Solid waste" not in key_evidence_part

    # ------------------------------------------------------------- #
    # Task 3: Metric Extraction Guardrail Assertions
    # ------------------------------------------------------------- #
    assert "### Relevant Financial Metrics" in final_ans
    metrics_part = final_ans.split("### Relevant Financial Metrics")[1].split("###")[0]
    # Guardrail: Suppress generic error
    assert "No relevant financial metric was identified in the retrieved evidence" not in metrics_part
    # Must explicitly list EBITDA and Margin
    assert "Adjusted EBITDA" in metrics_part
    assert "155.7" in metrics_part
    assert "10.3%" in metrics_part

    # ------------------------------------------------------------- #
    # Task 4: Explanation Remediation Assertions
    # ------------------------------------------------------------- #
    assert "### Explanation" in final_ans
    explanation_part = final_ans.split("### Explanation")[1].split("###")[0].strip()
    direct_ans_part = final_ans.split("### Answer / Direct Answer")[1].split("###")[0].strip()

    # Explanation must NOT repeat Direct Answer word-for-word
    assert explanation_part != direct_ans_part
    assert direct_ans_part not in explanation_part
    # Explanation must provide financial/operational context
    assert any(term in explanation_part.lower() for term in ["profitability", "operating", "margin", "efficiency", "revenue", "cash"])
