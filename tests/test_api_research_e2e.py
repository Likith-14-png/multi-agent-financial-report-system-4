from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_real_upload_produces_research_evidence_for_company():
    report_path = Path(__file__).resolve().parent / "fixtures" / "mock_financial_report_2024_2025.pdf"
    response = client.post(
        "/analysis/upload",
        files={"file": (report_path.name, report_path.read_bytes(), "application/pdf")},
        data={
            "company_name": "Nova Tech Systems Ltd.",
            "report_year": "2025",
            "question": "What are the company's main financial trends and risks in 2025 compared with 2024?",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["success"] is True
    assert body["analysis"]["analysis_id"]
    assert body["analysis"]["document_id"]
    assert body["research"]
    assert body["research"]["findings"]
    assert body["research"]["evidence"]
    assert body["research"]["source_chunks"]
    assert all(isinstance(chunk, str) and chunk.strip() for chunk in body["research"]["source_chunks"])
    assert "No indexed documents contain evidence" not in str(body["research"]["summary"])
    assert "Nova Tech Systems Ltd." in str(body["research"]["summary"]) or "Nova Tech Systems Ltd." in str(body["research"]["findings"])
