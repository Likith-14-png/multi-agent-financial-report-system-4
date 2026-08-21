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

    assert body["status"] == "success"
    analysis_id = body["analysis_id"]
    document_id = body["document_id"]
    assert analysis_id
    assert document_id

    # Retrieve baseline research
    res_resp = client.get(f"/analysis/{analysis_id}/research")
    assert res_resp.status_code == 200, res_resp.text
    res_body = res_resp.json()

    assert res_body["analysis_id"] == analysis_id
    assert res_body.get("findings") is not None
    assert res_body.get("evidence") is not None
    assert res_body.get("source_chunks") is not None
    assert all(isinstance(chunk, str) and chunk.strip() for chunk in res_body["source_chunks"])
    assert "No indexed documents contain evidence" not in str(res_body.get("summary", ""))

    # Query research via query endpoint
    query_resp = client.post(
        f"/analysis/{analysis_id}/research/query",
        json={"question": "What are the company's main financial trends and risks in 2025 compared with 2024?"},
    )
    assert query_resp.status_code == 200, query_resp.text
    query_body = query_resp.json()
    assert query_body["analysis_id"] == analysis_id
    assert query_body["question"] == "What are the company's main financial trends and risks in 2025 compared with 2024?"
    assert query_body["answer"]
    assert query_body["sources"]

