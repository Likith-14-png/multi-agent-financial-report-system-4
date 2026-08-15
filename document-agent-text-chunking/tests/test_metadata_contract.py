from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from document_agent import DocumentAgent, DocumentAgentConfig


def make_agent():
    agent = object.__new__(DocumentAgent)
    agent.config = DocumentAgentConfig()
    return agent


def build_metadata(agent, source_name="Example Annual Report 2024.txt", analysis_id="analysis-a", id_prefix="chunk"):
    path = Path(source_name)
    pages = [
        {
            "page_number": 1,
            "text": (
                "Annual Report 2024\n"
                "Example Manufacturing Holdings Ltd.\n"
                "For the year ended March 31, 2024\n\n"
                "Management Discussion and Analysis\n"
                "Revenue was $10 million and net income was $1 million."
            ),
            "content_length": 210,
        },
        {
            "page_number": 2,
            "text": (
                "Balance Sheet\n"
                "Metric | 2024 | 2023\n"
                "Total Assets | 100 | 90\n"
                "Total Liabilities | 40 | 35\n"
                "Figure 1 shows liquidity trends."
            ),
            "content_length": 130,
        },
    ]
    chunks = [
        {
            "text": pages[0]["text"],
            "page_numbers": [1],
            "block_types": ["narrative"],
            "section_title": "Management Discussion and Analysis",
            "section_type": "management_discussion",
        },
        {
            "text": pages[1]["text"],
            "page_numbers": [2],
            "block_types": ["table"],
            "section_title": "Balance Sheet",
            "section_type": "financial_statement",
        },
    ]
    full_text = "\n\n".join(page["text"] for page in pages)
    return agent._build_chunk_metadata(path, "hash-a", chunks, analysis_id, pages, [f"{id_prefix}-1", f"{id_prefix}-2"], full_text)


def test_chunk_metadata_uses_canonical_schema_and_legacy_aliases():
    agent = make_agent()
    metadatas = build_metadata(agent)
    first = metadatas[0]

    assert first["analysis_id"] == "analysis-a"
    assert first["document_id"]
    assert first["doc_type"] == first["report_type"] == "Annual Report"
    assert first["company_name"] == "Example Manufacturing Holdings Ltd."
    assert first["report_year"] == "2024"
    assert first["financial_year"] == "2024"
    assert first["report_period"] == "March 31, 2024"
    assert first["page_number"] == "1"
    assert first["previous_chunk_id"] == ""
    assert first["next_chunk_id"] == "chunk-2"
    assert "Revenue" in first["financial_metrics"]
    assert first["is_table"] is False
    assert first["contains_table"] == "false"


def test_table_chart_detection_and_validation_report():
    agent = make_agent()
    metadatas = build_metadata(agent)
    second = metadatas[1]

    assert second["previous_chunk_id"] == "chunk-1"
    assert second["next_chunk_id"] == ""
    assert second["is_table"] is True
    assert second["is_financial_table"] is True
    assert second["is_chart"] is True
    assert "Total Assets" in second["financial_metrics"]

    report = agent.build_quality_report(metadatas)
    assert report["total_documents"] == 1
    assert report["total_chunks"] == 2
    assert report["broken_chunk_links"] == 0
    assert report["cross_document_links"] == 0
    assert report["cross_analysis_links"] == 0
    assert report["embedding_dimensions"] == 384


def test_validation_detects_cross_analysis_links():
    agent = make_agent()
    left = build_metadata(agent, analysis_id="analysis-a")
    right = build_metadata(agent, source_name="Other Annual Report 2025.txt", analysis_id="analysis-b", id_prefix="other")
    left[-1]["next_chunk_id"] = right[0]["chunk_id"]

    validation = agent.validate_metadata(left + right)

    assert validation["cross_analysis_links"] == 1
    assert validation["cross_document_links"] == 1


def test_unknown_company_and_report_year_are_explicit():
    agent = make_agent()
    doc = agent._document_metadata(
        Path("mystery.txt"),
        "This document discusses operations without a cover page or fiscal date.",
        [{"page_number": 1, "text": "This document discusses operations without a cover page or fiscal date."}],
    )

    assert doc["company_name"] == "Unknown"
    assert doc["report_year"] == "Unknown"
    assert doc["report_period"] == "Unknown"
