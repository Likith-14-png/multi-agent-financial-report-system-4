from pathlib import Path

from backend.orchestration.workflow import AnalysisWorkflow
from red_flag_agent.app.models.response import RedFlagAnalysisResponse


def test_document_extraction_chromadb_research_red_flag_integration(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    report_path = Path(__file__).resolve().parent.parent / "data" / "abb_2025_report.txt"

    workflow = AnalysisWorkflow(
        chroma_path=str(tmp_path / "shared_chroma"),
        collection_name="abb_red_flag_integration_test",
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
    assert result["research"]["answer"]
    assert result["research"]["sources"]

    collection = workflow.document_agent.collection
    assert collection is not None
    data = collection.get(include=["documents", "metadatas"])
    assert data["documents"]
    assert any(doc for doc in data["documents"] if doc and len(doc.strip()) > 0)

    red_flags = result["red_flags"]
    assert red_flags["overall_risk"]
    assert red_flags["total_flags"] is not None
    assert isinstance(red_flags["flags"], list)
    assert red_flags["model_used"] == "offline-fallback"

    response = RedFlagAnalysisResponse(**red_flags)
    assert response.flags
    for flag in response.flags:
        assert flag.category
        assert flag.severity
        assert flag.title
        assert flag.evidence
        assert flag.recommendation
        assert flag.confidence >= 0
