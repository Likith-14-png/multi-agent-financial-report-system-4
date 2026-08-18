from pathlib import Path

from backend.orchestration.workflow import AnalysisWorkflow


def test_three_agent_vertical_slice(tmp_path):
    report_path = Path(__file__).resolve().parent.parent / "data" / "abb_2025_report.txt"
    workflow = AnalysisWorkflow(
        chroma_path=str(tmp_path / "shared_chroma"),
        collection_name="abb_integration_test",
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
    assert result["report_year"] == "2025"
    assert result["answer"]
    assert result["sources"]
    assert any(item.get("chunk_id") for item in result["sources"])
