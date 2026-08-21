import io
from pathlib import Path
from fastapi.testclient import TestClient

from backend.api import app
from backend.orchestration.session_store import session_store

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent
SAMPLE_REPORT_ABB = ROOT / "data" / "abb_2025_report.txt"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in {"healthy", "ok"}
    assert "financial-analysis-api" in str(data.get("service", "")) or "service" in data


def test_upload_analysis_and_endpoint_lifecycle(tmp_path):
    session_store.clear()
    assert SAMPLE_REPORT_ABB.exists(), f"Sample report missing at {SAMPLE_REPORT_ABB}"

    # 1. Upload valid document
    with open(SAMPLE_REPORT_ABB, "rb") as f:
        file_content = f.read()

    response = client.post(
        "/analysis/upload",
        files={"file": ("abb_2025_report.txt", file_content, "text/plain")},
        data={"company_name": "ABB", "report_year": "2025", "question": "What are the major developments?"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] in {"completed", "success"}
    analysis_id = data.get("analysis_id") or data["analysis"]["analysis_id"]
    document_id = data.get("document_id") or data["analysis"]["document_id"]
    assert analysis_id
    assert document_id

    # Verify Document Agent details in upload response
    assert "chunks" in data
    assert "collection" in data
    assert "quality_report" in data
    assert "embeddings" not in data

    # 2. Check Status Endpoint
    status_resp = client.get(f"/analysis/{analysis_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["analysis_id"] == analysis_id
    assert status_data["status"] == "completed"
    assert status_data["progress"] == 100

    # 3. Check Extraction Endpoint
    ext_resp = client.get(f"/analysis/{analysis_id}/extraction")
    assert ext_resp.status_code == 200
    ext_data = ext_resp.json()
    assert ext_data["analysis_id"] == analysis_id
    assert ext_data["company_name"] == "ABB"
    assert ext_data.get("revenue") == "$15.3 billion"
    assert ext_data.get("operating_income") == "$2.1 billion"
    assert ext_data.get("total_assets") == "$22.6 billion"
    assert ext_data.get("total_liabilities") == "$9.8 billion"

    # 4. Check Research Endpoint
    res_resp = client.get(f"/analysis/{analysis_id}/research")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["analysis_id"] == analysis_id
    assert res_data["answer"]
    assert isinstance(res_data["sources"], list)

    # 5. Check Research Query Endpoint
    query_resp = client.post(
        f"/analysis/{analysis_id}/research/query",
        json={"question": "What is the revenue for ABB?"},
    )
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["analysis_id"] == analysis_id
    assert query_data["answer"]
    assert isinstance(query_data["sources"], list)

    # 6. Check Red Flags Endpoint
    rf_resp = client.get(f"/analysis/{analysis_id}/red-flags")
    assert rf_resp.status_code == 200
    rf_data = rf_resp.json()
    assert rf_data["analysis_id"] == analysis_id
    assert "overall_risk" in rf_data
    assert "flags" in rf_data

    # 7. Check Red Flags Query Endpoint
    rf_query_resp = client.post(
        f"/analysis/{analysis_id}/red-flags/query",
        json={"question": "What are the supply chain risks?"},
    )
    assert rf_query_resp.status_code == 200
    rf_query_data = rf_query_resp.json()
    assert rf_query_data["analysis_id"] == analysis_id
    assert rf_query_data["answer"]

    # 8. Check Comparison Initial State (should be 404 before uploading Company B)
    cmp_init = client.get(f"/analysis/{analysis_id}/comparison")
    assert cmp_init.status_code == 404

    # 9. Upload Second Company Document for Comparison
    comp_content = b"""Infosys Financial Report 2025
Revenue increased to $18.5 billion in fiscal year 2025.
Operating income was $3.8 billion.
Net income reached $3.1 billion.
Total assets stood at $16.2 billion with total liabilities of $4.5 billion.
Operating cash flow remained robust at $3.2 billion.
EPS increased to $0.75 per share.
Risk factors include currency volatility and tech spending moderation.
"""
    comp_resp = client.post(
        f"/analysis/{analysis_id}/comparison/upload",
        files={"file": ("infosys_2025_report.txt", comp_content, "text/plain")},
        data={"company_name": "Infosys", "report_year": "2025"},
    )
    assert comp_resp.status_code == 200, comp_resp.text
    comp_data = comp_resp.json()
    assert comp_data["analysis_id"] == analysis_id
    assert comp_data["comparison_id"]
    assert "ABB" in comp_data["companies"]
    assert "Infosys" in comp_data["companies"]

    # 10. Check Comparison Result Endpoint
    cmp_after = client.get(f"/analysis/{analysis_id}/comparison")
    assert cmp_after.status_code == 200
    cmp_after_data = cmp_after.json()
    assert cmp_after_data["analysis_id"] == analysis_id
    assert len(cmp_after_data["companies"]) == 2
    assert "records" in cmp_after_data or "metrics" in cmp_after_data

    # 11. Check Report JSON Endpoint
    rep_resp = client.get(f"/analysis/{analysis_id}/report")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["analysis_id"] == analysis_id
    assert "executive_summary" in rep_data
    assert "financial_metrics" in rep_data
    assert rep_data["report_status"] in {"complete", "partial"}

    # 12. Check Report Download PDF Endpoint
    download_resp = client.get(f"/analysis/{analysis_id}/report/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert len(download_resp.content) > 100


def test_api_validation_and_error_handling():
    # 1. Non-existent analysis ID returns 404
    non_existent = "non-existent-analysis-id-1234"
    assert client.get(f"/analysis/{non_existent}/status").status_code == 404
    assert client.get(f"/analysis/{non_existent}/extraction").status_code == 404
    assert client.get(f"/analysis/{non_existent}/research").status_code == 404
    assert client.post(f"/analysis/{non_existent}/research/query", json={"question": "Test"}).status_code == 404
    assert client.get(f"/analysis/{non_existent}/red-flags").status_code == 404
    assert client.post(f"/analysis/{non_existent}/red-flags/query", json={"question": "Test"}).status_code == 404
    assert client.get(f"/analysis/{non_existent}/comparison").status_code == 404
    assert client.get(f"/analysis/{non_existent}/report").status_code == 404
    assert client.get(f"/analysis/{non_existent}/report/download").status_code == 404

    # 2. Empty file upload returns 400
    empty_resp = client.post(
        "/analysis/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"company_name": "TestCo", "report_year": "2025"},
    )
    assert empty_resp.status_code == 400

    # 3. Unsupported file extension returns 400
    invalid_ext = client.post(
        "/analysis/upload",
        files={"file": ("invalid.exe", b"binary content", "application/octet-stream")},
        data={"company_name": "TestCo", "report_year": "2025"},
    )
    assert invalid_ext.status_code == 400


def test_session_isolation():
    session_store.clear()

    # Create Session A
    id_a = "session-abb-001"
    session_store.create_session(
        analysis_id=id_a,
        document_id="doc-abb-001",
        company_name="ABB",
        report_year="2025",
        status="completed",
        progress=100,
        extraction_result={"company_name": "ABB", "report_year": "2025", "revenue": "$32.8 billion", "net_income": "$3.2 billion"},
        research_result={"answer": "ABB delivered strong operating performance.", "sources": [{"snippet": "ABB snippet", "source_file": "abb.pdf"}]},
        red_flags_result={"overall_risk": "Low", "total_flags": 1, "flags": [{"category": "Risk", "description": "Supply chain"}]},
        report_result={"executive_summary": "ABB 2025 summary"},
    )

    # Create Session B with distinct data
    id_b = "session-siemens-002"
    session_store.create_session(
        analysis_id=id_b,
        document_id="doc-siemens-002",
        company_name="Siemens",
        report_year="2025",
        status="completed",
        progress=100,
        extraction_result={"company_name": "Siemens", "report_year": "2025", "revenue": "$75.0 billion", "net_income": "$8.5 billion"},
        research_result={"answer": "Siemens saw revenue growth in digital industries.", "sources": [{"snippet": "Siemens snippet", "source_file": "siemens.pdf"}]},
        red_flags_result={"overall_risk": "Medium", "total_flags": 3, "flags": [{"category": "Market", "description": "Tech transition"}]},
        report_result={"executive_summary": "Siemens 2025 summary"},
    )

    assert id_a != id_b

    # Verify extraction endpoint isolation
    ext_a = client.get(f"/analysis/{id_a}/extraction").json()
    ext_b = client.get(f"/analysis/{id_b}/extraction").json()

    assert ext_a["analysis_id"] == id_a
    assert ext_b["analysis_id"] == id_b
    assert ext_a["company_name"] == "ABB"
    assert ext_b["company_name"] == "Siemens"

    # Verify research endpoint isolation
    res_a = client.get(f"/analysis/{id_a}/research").json()
    res_b = client.get(f"/analysis/{id_b}/research").json()
    assert "ABB" in res_a["answer"]
    assert "Siemens" in res_b["answer"]

    # Verify red flags endpoint isolation
    rf_a = client.get(f"/analysis/{id_a}/red-flags").json()
    rf_b = client.get(f"/analysis/{id_b}/red-flags").json()
    assert rf_a["overall_risk"] == "Low"
    assert rf_b["overall_risk"] == "Medium"
    assert rf_a["total_flags"] == 1
    assert rf_b["total_flags"] == 3
