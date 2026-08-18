from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.api import app
from backend.orchestration.session_store import session_store

client = TestClient(app)


class FakeWorkflow:
    comparison_called = False

    def __init__(self, *args, **kwargs):
        pass

    def run_initial_analysis(self, report_path, *, analysis_id, document_id, company_name=None, report_year=None, question=None):
        company = company_name or "ABB"
        year = report_year or 2025
        return {
            "analysis_id": analysis_id,
            "document_id": document_id,
            "company_name": company,
            "report_year": year,
            "extraction": {"company_name": company, "report_year": year, "revenue": "$15.3 billion", "metrics": [{"metric": "Revenue", "value": 15.3, "unit": "billion"}]},
            "research": {"answer": "Revenue increased based on the indexed report.", "sources": [{"chunk_id": "chunk-1", "snippet": "Revenue increased."}], "evidence": [{"chunk_id": "chunk-1", "snippet": "Revenue increased."}]},
            "red_flags": {"overall_risk": "Low", "total_flags": 0, "flags": [], "model_used": "offline-fallback"},
            "comparison": {"comparison_type": "pending", "records": []},
            "report": {"report_status": "complete", "company_name": company, "report_year": year, "comparison": {}, "research": {"evidence": [{"chunk_id": "chunk-1", "snippet": "Revenue increased."}]}},
        }

    def run_research_query(self, analysis, question):
        return {"answer": f"Answer for: {question}", "sources": [{"chunk_id": "chunk-1", "snippet": "Evidence"}], "evidence": [{"chunk_id": "chunk-1", "snippet": "Evidence"}]}

    def run_red_flags_query(self, analysis, question):
        return {"overall_risk": "Medium", "total_flags": 1, "flags": [{"title": question}], "model_used": "offline-fallback"}

    def run_comparison_upload(self, *, analysis_id, original_extraction, report_path, document_id):
        FakeWorkflow.comparison_called = True
        return {
            "document_id": document_id,
            "comparison_id": str(uuid4()),
            "company_name": "Infosys",
            "report_year": 2025,
            "extraction": {"document_id": document_id, "company_name": "Infosys", "report_year": 2025, "revenue": "$20 billion"},
            "comparison": {"comparison_type": "cross_company", "companies": ["ABB", "Infosys"], "records": [{"metric": "Revenue"}], "summary": {"metrics_compared": 1}},
        }

    def generate_comparison_report(self, **kwargs):
        return {"report_status": "complete", "comparison": kwargs["comparison"], "research": {"evidence": []}}

    def generate_pdf_report(self, report, output_file):
        Path(output_file).write_bytes(b"%PDF-1.4\n% fake test pdf\n")
        return output_file


def _upload(filename="report.pdf", content=b"%PDF-1.4 test", content_type="application/pdf", **data):
    return client.post("/analysis/upload", files={"file": (filename, content, content_type)}, data=data)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "financial-analysis-api"
    assert response.json()["status"] == "ok"


def test_file_only_upload_returns_clean_response_and_does_not_expose_chroma_internals(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    response = _upload()
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"analysis_id", "document_id", "status", "message"}
    assert body["status"] == "completed"
    serialized = response.text.lower()
    assert "embedding" not in serialized
    assert "chromadb" not in serialized
    assert "chunks" not in serialized
    assert "enterprise_chroma_db" not in serialized


def test_legacy_upload_fields_remain_supported(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    response = _upload(company_name="ABB", report_year="2025", question="What changed?")
    assert response.status_code == 200
    assert response.json()["analysis"]["company_name"] == "ABB"
    assert response.json()["analysis"]["report_year"] == 2025


def test_status_extraction_research_red_flags_and_report(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    response = _upload()
    analysis_id = response.json()["analysis_id"]

    status = client.get(f"/analysis/{analysis_id}/status")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    extraction = client.get(f"/analysis/{analysis_id}/extraction")
    assert extraction.status_code == 200
    assert extraction.json()["metrics"]

    research = client.get(f"/analysis/{analysis_id}/research")
    assert research.status_code == 200
    assert research.json()["answer"]

    red_flags = client.get(f"/analysis/{analysis_id}/red-flags")
    assert red_flags.status_code == 200
    assert red_flags.json()["overall_risk"] == "Low"

    report = client.get(f"/analysis/{analysis_id}/report")
    assert report.status_code == 200
    assert report.json()["report"]["report_status"] == "complete"


def test_research_and_red_flag_queries_use_existing_workflow(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    analysis_id = _upload().json()["analysis_id"]

    research = client.post(f"/analysis/{analysis_id}/research/query", json={"question": "Why did revenue increase?"})
    assert research.status_code == 200
    assert "Why did revenue increase?" in research.json()["answer"]

    red_flags = client.post(f"/analysis/{analysis_id}/red-flags/query", json={"question": "Why is liquidity a risk?"})
    assert red_flags.status_code == 200
    assert red_flags.json()["total_flags"] == 1


def test_comparison_is_not_run_on_initial_upload_and_second_document_gets_new_id(monkeypatch):
    FakeWorkflow.comparison_called = False
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    initial = _upload().json()
    assert FakeWorkflow.comparison_called is False

    response = client.post(
        f"/analysis/{initial['analysis_id']}/comparison/upload",
        files={"file": ("infosys.pdf", b"%PDF-1.4 second", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert FakeWorkflow.comparison_called is True
    assert body["document_id"] != initial["document_id"]
    assert body["analysis_id"] == initial["analysis_id"]

    comparison = client.get(f"/analysis/{initial['analysis_id']}/comparison")
    assert comparison.status_code == 200
    assert comparison.json()["comparison"]["comparison_type"] == "cross_company"


def test_report_download(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    analysis_id = _upload().json()["analysis_id"]
    response = client.get(f"/analysis/{analysis_id}/report/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_unknown_analysis_returns_404():
    response = client.get("/analysis/does-not-exist/status")
    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis not found."}


def test_session_isolation(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    first = _upload(company_name="ABB").json()
    second = _upload(company_name="Infosys").json()
    assert first["analysis_id"] != second["analysis_id"]

    first_status = client.get(f"/analysis/{first['analysis_id']}/status").json()
    second_status = client.get(f"/analysis/{second['analysis_id']}/status").json()
    assert first_status["analysis_id"] != second_status["analysis_id"]

    first_report = client.get(f"/analysis/{first['analysis_id']}/report").json()
    second_report = client.get(f"/analysis/{second['analysis_id']}/report").json()
    assert first_report["report"]["company_name"] == "ABB"
    assert second_report["report"]["company_name"] == "Infosys"


def test_invalid_uploads_are_rejected(monkeypatch):
    monkeypatch.setattr("backend.api.AnalysisWorkflow", FakeWorkflow)
    empty = client.post("/analysis/upload", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert empty.status_code == 400
    executable = client.post("/analysis/upload", files={"file": ("bad.pdf", b"MZfake", "application/pdf")})
    assert executable.status_code == 400
    unsupported = client.post("/analysis/upload", files={"file": ("bad.exe", b"data", "application/octet-stream")})
    assert unsupported.status_code == 400
