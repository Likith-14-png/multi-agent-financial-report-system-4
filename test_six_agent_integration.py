from pathlib import Path

from backend.orchestration.workflow import AnalysisWorkflow


def test_document_extraction_chromadb_research_red_flag_comparison_report_integration(tmp_path, monkeypatch):
    
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    report_path = Path(__file__).resolve().parent / "data" / "abb_2025_report.txt"

    workflow = AnalysisWorkflow(
        chroma_path=str(tmp_path / "shared_chroma"),
        collection_name="abb_report_integration_test",
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

    assert result["extraction"]
    assert result["research"]["answer"]
    assert result["research"]["sources"]
    assert result["red_flags"]["overall_risk"]
    assert result["red_flags"]["total_flags"] is not None
    assert isinstance(result["red_flags"]["flags"], list)
    assert result["comparison"] is not None

    assert "report" in result
    report = result["report"]
    assert report["company_name"] == "ABB"
    assert report["report_year"] == 2025
    assert report["analysis_id"] == result["analysis_id"]
    assert report["document_id"] == result["document_id"]

    assert report["extraction"]["revenue"]
    assert report["research"]["answer"]
    assert report["red_flags"]["overall_risk"]
    assert result["red_flags"]["total_flags"] >= 1

    comparison_rows = report["comparison"]
    if isinstance(comparison_rows, list):
        comparison_map = {row.get("Metric"): row.get("Value") for row in comparison_rows}
    else:
        comparison_map = {row["Metric"]: row["Value"] for row in comparison_rows.to_dict(orient="records")}

    assert "Revenue" in comparison_map
    assert "Operating Income" in comparison_map
    assert "Total Assets" in comparison_map
    assert "Total Liabilities" in comparison_map

    assert report["metadata"]["analysis_id"] == result["analysis_id"]
    assert report["metadata"]["document_id"] == result["document_id"]
    assert report["metadata"]["company_name"] == "ABB"
    assert str(report["metadata"]["report_year"]) == "2025"

    metadata_sample = data["metadatas"][0]
    assert metadata_sample.get("analysis_id") == result["analysis_id"] or metadata_sample.get("analysis_id")
    assert metadata_sample.get("document_id") == result["document_id"] or metadata_sample.get("document_id")
    assert metadata_sample.get("company_name") == "ABB"
    assert str(metadata_sample.get("report_year")) == "2025"
