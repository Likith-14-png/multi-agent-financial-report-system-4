from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import app
from backend.orchestration.session_store import session_store


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_report_download_returns_valid_pdf_signature():
    session_store.clear()
    report_path = ROOT / "data" / "abb_2025_report.txt"
    response = client.post(
        "/analysis/upload",
        files={"file": (report_path.name, report_path.read_bytes(), "text/plain")},
        data={"company_name": "ABB", "report_year": "2025"},
    )
    assert response.status_code == 200, response.text
    analysis_id = response.json()["analysis_id"]

    download = client.get(f"/analysis/{analysis_id}/report/download")

    assert download.status_code == 200, download.text
    assert "application/pdf" in download.headers["content-type"]
    assert download.content.startswith(b"%PDF")
    assert len(download.content) > 100
