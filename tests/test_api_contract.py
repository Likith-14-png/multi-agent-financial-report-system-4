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

    assert body["success"] is True
    assert body["analysis"]["company_name"] == "ABB"
    assert body["analysis"]["report_year"] == 2025
    assert body["metadata"]["analysis_id"] == body["analysis"]["analysis_id"]
    assert body["metadata"]["document_id"] == body["analysis"]["document_id"]

    assert "metrics" in body["extraction"]
    metrics = body["extraction"]["metrics"]
    assert any(metric.get("metric") == "Revenue" and metric.get("value") == 15.3 for metric in metrics)
    assert any(metric.get("metric") == "Operating Income" and metric.get("value") == 2.1 for metric in metrics)
    assert any(metric.get("metric") == "Total Assets" and metric.get("value") == 22.6 for metric in metrics)
    assert any(metric.get("metric") == "Total Liabilities" and metric.get("value") == 9.8 for metric in metrics)

    assert body["research"]["summary"] or body["research"]["findings"] or body["research"]["evidence"]
    assert body["red_flags"]["model_used"] in {"offline-fallback", "gemini"}
    assert body["red_flags"]["overall_risk"]
    assert body["comparison"]["records"]
    assert body["comparison"]["comparison_type"] != "single_year"
    assert any(str(record.get("current_year")) == "2025" and str(record.get("previous_year")) == "2024" for record in body["comparison"]["records"])
    assert body["report"]["report_status"] in {"complete", "partial"}
    assert body["report"]["comparison"]
    assert json.dumps(body)


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
    extraction = response.json()["report"]["extraction"]

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
    body = response.json()

    top_level_evidence = body["research"]["evidence"]
    report_research_evidence = body["report"]["research"]["evidence"]

    assert top_level_evidence
    assert report_research_evidence is not None
    assert report_research_evidence == top_level_evidence
    assert len(report_research_evidence) == len(top_level_evidence)
    assert len(report_research_evidence) == len({json.dumps(item, sort_keys=True) for item in report_research_evidence})


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
