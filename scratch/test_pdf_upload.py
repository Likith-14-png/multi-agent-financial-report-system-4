import httpx
import os

BASE_URL = "http://127.0.0.1:8000"

def test_pdf_upload():
    pdf_path = "tests/fixtures/mock_financial_report_2024_2025.pdf"
    if not os.path.exists(pdf_path):
        pdf_path = "document-agent-text-chunking/scripts/demo_data/2024_Annual_Report.pdf"
    
    print(f"Testing real PDF ingestion with {pdf_path}...")
    assert os.path.exists(pdf_path), f"PDF file not found at {pdf_path}"

    client = httpx.Client(base_url=BASE_URL, timeout=120.0)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res = client.post(
        "/analysis/upload",
        files={"file": (os.path.basename(pdf_path), pdf_bytes, "application/pdf")},
        data={"company_name": "Acme Corp", "report_year": "2024"}
    )
    print("PDF Upload Status:", res.status_code)
    assert res.status_code == 200, res.text
    data = res.json()
    analysis_id = data.get("analysis_id")
    print("Ingested PDF Analysis ID:", analysis_id, "Total Chunks:", data.get("total_chunks"))
    assert analysis_id
    assert data.get("total_chunks", 0) > 0

    # Retrieve extraction
    ext_res = client.get(f"/analysis/{analysis_id}/extraction")
    print("PDF Extraction Status:", ext_res.status_code)
    assert ext_res.status_code == 200

    # Retrieve report download
    pdf_res = client.get(f"/analysis/{analysis_id}/report/download")
    print("PDF Report Download Status:", pdf_res.status_code, "Bytes:", len(pdf_res.content))
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-")
    print("REAL PDF INGESTION AND ROUND-TRIP REPORT DOWNLOAD VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_pdf_upload()
