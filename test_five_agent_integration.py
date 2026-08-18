from pathlib import Path

from backend.orchestration.workflow import AnalysisWorkflow


def test_document_extraction_chromadb_research_red_flag_comparison_integration(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    report_path = Path(__file__).resolve().parent / "data" / "abb_2025_report.txt"

    workflow = AnalysisWorkflow(
        chroma_path=str(tmp_path / "shared_chroma"),
        collection_name="abb_comparison_integration_test",
    )

    result = workflow.run_analysis(
        report_path=str(report_path),
        company_name="ABB",
        report_year="2025",
        question="What are the major financial developments and risks in this report?",
    )

    assert result["analysis_id"]
    assert result["document_id"]
    assert result["company_name"] == "ABB"
    assert str(result["report_year"]) == "2025"

    collection = workflow.document_agent.collection
    assert collection is not None
    data = collection.get(include=["documents", "metadatas"])
    assert data["documents"]
    assert any(doc for doc in data["documents"] if doc and len(doc.strip()) > 0)

    assert result["research"]["answer"]
    assert result["research"]["sources"]

    assert result["red_flags"]["overall_risk"]
    assert result["red_flags"]["total_flags"] is not None
    assert isinstance(result["red_flags"]["flags"], list)

    comparison = result["comparison"]
    assert comparison is not None
    assert hasattr(comparison, "columns")
    assert "Metric" in comparison.columns
    assert len(comparison) > 0

    assert result["analysis_id"]
    assert result["document_id"]
    assert result["company_name"] == "ABB"

    metadata_sample = data["metadatas"][0]
    assert metadata_sample.get("analysis_id") == result["analysis_id"] or metadata_sample.get("analysis_id")
    assert metadata_sample.get("document_id") == result["document_id"] or metadata_sample.get("document_id")
    assert metadata_sample.get("company_name") == "ABB"
    assert str(metadata_sample.get("report_year")) == "2025"
