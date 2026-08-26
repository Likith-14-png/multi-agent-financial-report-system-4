from fastapi.testclient import TestClient

import backend.api as api
from backend.orchestration.context import AnalysisContextStore


client = TestClient(api.app)


class FakeWorkflow:
    def __init__(self, **_kwargs):
        pass

    def ingest_document(self, _path, company, year):
        return {"metadata": {"company_name": company, "report_year": int(year)}, "chunks": []}

    @staticmethod
    def extract_metrics(_text, metadata):
        return {"revenue": "15 billion", **metadata}

    @staticmethod
    def analyze_red_flags(_company, _chunks):
        return {"overall_risk": "Low", "flags": []}

    def research(self, question, _company, _top_k):
        return {"answer": question, "evidence": [], "source_chunks": []}

    @staticmethod
    def compare_companies(companies):
        return {"comparison_type": "peer_benchmarking", "records": [{"companies": companies}]}

    @staticmethod
    def generate_report(_extraction, _research, _red_flags, _comparison, metadata):
        return {"metadata": metadata, "report_status": "complete"}

    def run_analysis(self, **_kwargs):
        return {"analysis_id": "a", "document_id": "d", "company_name": "ABB", "report_year": 2025,
                "metadata": {}, "extraction": {}, "research": {}, "red_flags": {}, "comparison": {}, "report": {}}


def test_document_endpoint_calls_workflow(monkeypatch):
    monkeypatch.setattr(api, "AnalysisWorkflow", FakeWorkflow)
    response = client.post("/analysis/document", files={"file": ("report.pdf", b"pdf", "application/pdf")}, data={"company_name": "ABB", "report_year": "2025"})
    assert response.status_code == 200
    assert response.json()["metadata"]["company_name"] == "ABB"


def test_individual_agent_json_endpoints(monkeypatch):
    monkeypatch.setattr(api, "AnalysisWorkflow", FakeWorkflow)

    assert client.post("/analysis/extraction", json={"text": "Revenue 15 billion", "metadata": {"company_name": "ABB"}}).status_code == 200
    assert client.post("/analysis/red-flags", json={"company_name": "ABB", "context_chunks": [{"document": "text", "metadata": {}}]}).status_code == 200
    assert client.post("/analysis/research", json={"company_name": "ABB", "question": "What are the risks?"}).status_code == 200
    comparison = client.post("/analysis/comparison", json={"companies": [{"company_name": "ABB", "report_year": 2025}, {"company_name": "Beta", "report_year": 2025}]})
    assert comparison.status_code == 200
    report = client.post("/analysis/report", json={"metadata": {"analysis_id": "a", "document_id": "d", "company_name": "ABB", "report_year": 2025}})
    assert report.status_code == 200


def test_upload_endpoint_still_uses_workflow(monkeypatch):
    monkeypatch.setattr(api, "AnalysisWorkflow", FakeWorkflow)
    response = client.post("/analysis/upload", files={"file": ("report.pdf", b"pdf", "application/pdf")}, data={"company_name": "ABB", "report_year": "2025", "question": "Risks?"})
    assert response.status_code == 200
    assert response.json()["success"] is True


class ContextWorkflow(FakeWorkflow):
    def ingest_document(self, _path, company, year):
        analysis_id = f"analysis-{company.lower()}"
        document_id = f"document-{company.lower()}"
        return {
            "metadata": {"analysis_id": analysis_id, "document_id": document_id,
                         "company_name": company, "report_year": int(year)},
            "document": {"source_file": f"{company.lower()}.pdf"},
            "chunks": [{"text": f"{company} revenue 15 billion", "metadata": {"chunk_id": f"{company.lower()}-chunk"}}],
        }

    def extract_context(self, context):
        return {"revenue": "15 billion", "analysis_id": context.analysis_id,
                "document_id": context.document_id, "company_name": context.company_name,
                "report_year": context.report_year, "source_chunks": [context.chunks[0]["metadata"]["chunk_id"]]}

    def red_flags_for_context(self, context):
        assert context.extraction["analysis_id"] == context.analysis_id
        return {"overall_risk": "Low", "flags": [], "metadata": self.context_metadata(context)}

    def research_for_context(self, context, question, _top_k):
        assert context.chunks[0]["text"].startswith(context.company_name)
        return {"answer": question, "findings": ["grounded"], "evidence": [], "source_chunks": [],
                "metadata": self.context_metadata(context, question)}

    @staticmethod
    def context_metadata(context, question=None):
        payload = {"analysis_id": context.analysis_id, "document_id": context.document_id,
                   "company_name": context.company_name, "report_year": context.report_year}
        if question:
            payload["question"] = question
        return payload

    @staticmethod
    def comparison_input(context):
        return {"analysis_id": context.analysis_id, "document_id": context.document_id,
                "company_name": context.company_name, "report_year": context.report_year,
                "extracted_metrics": context.extraction}

    @staticmethod
    def generate_report(extraction, research, red_flags, comparison, metadata):
        assert extraction and research and red_flags and comparison
        return {"metadata": metadata, "report_status": "complete", "extraction": extraction}


def test_agent_endpoints_share_analysis_context(monkeypatch):
    """The Swagger sequence passes IDs only; no data is copied between calls."""
    monkeypatch.setattr(api, "AnalysisWorkflow", ContextWorkflow)
    monkeypatch.setattr(api, "analysis_context_store", AnalysisContextStore())

    document = client.post("/analysis/document", files={"file": ("abb.pdf", b"pdf", "application/pdf")},
                           data={"company_name": "ABB", "report_year": "2025", "question": "What changed?"})
    assert document.status_code == 200
    ids = document.json()
    analysis_id, document_id = ids["analysis_id"], ids["document_id"]

    extraction = client.post("/analysis/extraction", json={"analysis_id": analysis_id, "document_id": document_id})
    assert extraction.status_code == 200
    assert extraction.json()["source_chunks"] == ["abb-chunk"]

    red_flags = client.post("/analysis/red-flags", json={"analysis_id": analysis_id})
    assert red_flags.status_code == 200 and red_flags.json()["overall_risk"] == "Low"

    research = client.post("/analysis/research", json={"analysis_id": analysis_id, "question": "What changed?"})
    assert research.status_code == 200 and research.json()["answer"] == "What changed?"

    comparison = client.post("/analysis/comparison", json={"analysis_id": analysis_id})
    assert comparison.status_code == 200
    report = client.post("/analysis/report", json={"analysis_id": analysis_id})
    assert report.status_code == 200 and report.json()["report_status"] == "complete"

    second = client.post("/analysis/document", files={"file": ("beta.pdf", b"pdf", "application/pdf")},
                         data={"company_name": "Beta", "report_year": "2025"}).json()
    assert client.post("/analysis/extraction", json={"analysis_id": second["analysis_id"], "document_id": second["document_id"]}).status_code == 200
    multi = client.post("/analysis/comparison", json={"analysis_ids": [analysis_id, second["analysis_id"]]})
    assert multi.status_code == 200
    assert multi.json()["records"][0]["companies"][0]["analysis_id"] == analysis_id

    missing = client.post("/analysis/extraction", json={"analysis_id": "missing", "document_id": "missing"})
    assert missing.status_code == 404
    assert "Run /analysis/document first" in missing.json()["error"]["message"]
