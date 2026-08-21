import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import app
from backend.orchestration.workflow import AnalysisWorkflow

client = TestClient(app)


def _abb_upload_payload():
    report_path = Path(__file__).resolve().parent.parent / "data" / "abb_2025_report.txt"
    return {
        "file": (report_path.name, report_path.read_bytes(), "text/plain"),
        "data": {"company_name": "ABB", "report_year": "2025", "question": "What are the major financial developments and risks in this report?"},
    }


def test_upload_analysis_returns_canonical_success_response():
    payload = _abb_upload_payload()

    response = client.post(
        "/analysis/upload",
        files={"file": payload["file"]},
        data=payload["data"],
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "success"
    assert body["company_name"] == "ABB"
    assert str(body["report_year"]) == "2025"
    assert body["analysis_id"]
    assert body["document_id"]
    assert body["collection"] == "financial_research_v1"
    assert body["total_chunks"] > 0
    assert "chunks" in body
    assert "quality_report" in body
    assert json.dumps(body)

    # Verify downstream fields are NOT in upload response
    assert "extraction" not in body
    assert "research" not in body
    assert "red_flags" not in body
    assert "comparison" not in body
    assert "report" not in body

    analysis_id = body["analysis_id"]

    # Extraction endpoint verification
    ext_resp = client.get(f"/analysis/{analysis_id}/extraction")
    assert ext_resp.status_code == 200
    ext_body = ext_resp.json()
    assert ext_body.get("revenue") == "$15.3 billion"
    assert ext_body.get("operating_income") == "$2.1 billion"
    assert ext_body.get("total_assets") == "$22.6 billion"
    assert ext_body.get("total_liabilities") == "$9.8 billion"

    # Research endpoint verification
    res_resp = client.get(f"/analysis/{analysis_id}/research")
    assert res_resp.status_code == 200
    res_body = res_resp.json()
    assert res_body.get("answer") or res_body.get("summary") or res_body.get("findings")

    # Red Flags endpoint verification
    rf_resp = client.get(f"/analysis/{analysis_id}/red-flags")
    assert rf_resp.status_code == 200
    rf_body = rf_resp.json()
    assert rf_body.get("model_used") in {"offline-fallback", "gemini"}
    assert rf_body.get("overall_risk")

    # Report endpoint verification
    rep_resp = client.get(f"/analysis/{analysis_id}/report")
    assert rep_resp.status_code == 200
    rep_body = rep_resp.json()
    assert rep_body.get("report_status") in {"complete", "partial"}
    assert rep_body.get("financial_metrics") or rep_body.get("extraction")


def test_extraction_uses_current_document_only_for_company_scope():
    workflow = AnalysisWorkflow(chroma_path=str(Path(__file__).resolve().parent.parent / "enterprise_chroma_db"), collection_name="financial_research_v1")

    class StubCollection:
        def __init__(self, records):
            self.records = records

        def get(self, where=None, include=None):
            if where == {"$and": [{"company_name": "ABB"}, {"document_id": "abb-doc-123"}]}:
                rows = [row for row in self.records if row[1].get("company_name") == "ABB" and row[1].get("document_id") == "abb-doc-123"]
            elif where == {"company_name": "ABB"}:
                rows = [row for row in self.records if row[1].get("company_name") == "ABB"]
            else:
                rows = []
            return {
                "documents": [row[0] for row in rows],
                "metadatas": [row[1] for row in rows],
            }

    stale_doc = "Operating Income increased to $5.5 billion. Revenue rose to $20.0 billion."
    abb_doc_1 = "Revenue increased to $15.3 billion in 2025. Operating income was $2.1 billion."
    abb_doc_2 = "Total assets were $22.6 billion and total liabilities were $9.8 billion."
    collection = StubCollection([
        (stale_doc, {"company_name": "Operating Income", "document_id": "stale-doc", "chunk_index": 0, "chunk_id": "stale-1"}),
        (abb_doc_1, {"company_name": "ABB", "document_id": "abb-doc-123", "chunk_index": 0, "chunk_id": "abb-1"}),
        (abb_doc_2, {"company_name": "ABB", "document_id": "abb-doc-123", "chunk_index": 1, "chunk_id": "abb-2"}),
    ])

    current_records = workflow._get_current_document_records(collection, "ABB", "abb-doc-123")
    assert len(current_records) == 2
    combined_text = "\n\n".join(doc for doc, _ in current_records)
    metrics = workflow.document_agent.__class__.__module__
    from extraction_agent import extract_report_metrics
    extracted = extract_report_metrics(combined_text, metadata=current_records[0][1])

    assert extracted.get("revenue")
    assert "$15.3 billion" in extracted.get("revenue")
    assert extracted.get("operating_income") and "$2.1 billion" in extracted.get("operating_income")
    assert extracted.get("total_assets") and "$22.6 billion" in extracted.get("total_assets")
    assert extracted.get("total_liabilities") and "$9.8 billion" in extracted.get("total_liabilities")
    assert "Operating Income" not in extracted.get("company_name", "") or extracted.get("company_name") == "ABB"


def test_report_extraction_snapshot_omits_ambiguous_duplicate_value_field():
    payload = _abb_upload_payload()
    response = client.post(
        "/analysis/upload",
        files={"file": payload["file"]},
        data=payload["data"],
    )

    assert response.status_code == 200, response.text
    analysis_id = response.json()["analysis_id"]

    rep_resp = client.get(f"/analysis/{analysis_id}/report")
    assert rep_resp.status_code == 200, rep_resp.text
    extraction = rep_resp.json()["extraction"]

    for key in ("revenue", "operating_income", "net_income", "total_assets", "total_liabilities", "cash_flow"):
        assert key in extraction
        value = extraction.get(key)
        assert value is None or isinstance(value, (str, int, float))

    assert "value" not in extraction


def test_report_research_evidence_matches_top_level_research_evidence():
    payload = _abb_upload_payload()
    response = client.post(
        "/analysis/upload",
        files={"file": payload["file"]},
        data=payload["data"],
    )

    assert response.status_code == 200, response.text
    analysis_id = response.json()["analysis_id"]

    res_resp = client.get(f"/analysis/{analysis_id}/research")
    assert res_resp.status_code == 200, res_resp.text
    res_body = res_resp.json()

    rep_resp = client.get(f"/analysis/{analysis_id}/report")
    assert rep_resp.status_code == 200, rep_resp.text
    rep_body = rep_resp.json()

    top_level_evidence = res_body.get("evidence") or res_body.get("sources")
    report_research_evidence = (rep_body.get("research", {}) or {}).get("evidence") or (rep_body.get("research", {}) or {}).get("sources")

    assert top_level_evidence
    assert report_research_evidence is not None
    assert len(report_research_evidence) == len(top_level_evidence)


def test_upload_requires_document_and_form_fields():
    response = client.post(
        "/analysis/upload",
        data={"company_name": "ABB", "report_year": "2025", "question": "Explain the risks."},
    )

    assert response.status_code in {400, 422}


def test_health_endpoint_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_document_agent_upload_openapi_schema_omits_optional_fields():
    schema = app.openapi()
    upload_body = schema["paths"]["/analysis/upload"]["post"]["requestBody"]
    schema_ref = upload_body["content"]["multipart/form-data"]["schema"]
    body_schema = schema["components"]["schemas"].get(schema_ref.get("$ref", "").split("/")[-1]) or schema_ref
    properties = body_schema.get("properties", {})

    assert "file" in properties
    assert "company_name" not in properties
    assert "report_year" not in properties
    assert "question" not in properties
