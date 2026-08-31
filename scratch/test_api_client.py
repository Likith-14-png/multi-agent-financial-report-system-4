import httpx
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_full_pipeline():
    print(f"Testing backend at {BASE_URL}...")
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    # 1. Health check
    res = client.get("/health")
    print("1. Health:", res.status_code, res.json())
    assert res.status_code == 200
    assert res.json().get("status") in {"ok", "healthy"}

    # 2. Upload Document A (ABB report)
    with open("data/abb_2025_report.txt", "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/analysis/upload",
        files={"file": ("abb_2025_report.txt", file_bytes, "text/plain")},
        data={"company_name": "ABB", "report_year": "2025", "question": "What is revenue growth?"}
    )
    print("2. Upload:", res.status_code)
    assert res.status_code == 200, res.text
    upload_data = res.json()
    analysis_id = upload_data.get("analysis_id")
    print("   analysis_id:", analysis_id)
    assert analysis_id
    assert upload_data.get("total_chunks", 0) > 0

    # 3. Status
    res = client.get(f"/analysis/{analysis_id}/status")
    print("3. Status:", res.status_code, res.json())
    assert res.status_code == 200
    assert res.json().get("status") == "completed"

    # 4. Extraction
    res = client.get(f"/analysis/{analysis_id}/extraction")
    print("4. Extraction:", res.status_code)
    assert res.status_code == 200
    ext_data = res.json()
    print("   company_name:", ext_data.get("company_name"))
    print("   revenue:", ext_data.get("revenue"))
    print("   operating_income:", ext_data.get("operating_income"))
    print("   total_assets:", ext_data.get("total_assets"))
    print("   total_liabilities:", ext_data.get("total_liabilities"))
    assert ext_data.get("revenue") is not None

    # 5. Research Baseline
    res = client.get(f"/analysis/{analysis_id}/research")
    print("5. Research baseline:", res.status_code)
    assert res.status_code == 200
    res_data = res.json()
    print("   answer snippet:", str(res_data.get("answer"))[:100])
    print("   sources count:", len(res_data.get("sources", [])))
    assert len(res_data.get("sources", [])) > 0

    # 6. Research Query
    res = client.post(
        f"/analysis/{analysis_id}/research/query",
        json={"question": "What drove revenue growth and what were the numbers?"}
    )
    print("6. Research Query:", res.status_code)
    assert res.status_code == 200
    query_data = res.json()
    print("   query answer snippet:", str(query_data.get("answer"))[:100])
    assert query_data.get("answer")

    # 7. Red Flags
    res = client.get(f"/analysis/{analysis_id}/red-flags")
    print("7. Red Flags:", res.status_code)
    assert res.status_code == 200
    rf_data = res.json()
    print("   overall_risk:", rf_data.get("overall_risk"))
    print("   total_flags:", rf_data.get("total_flags"))
    assert "overall_risk" in rf_data

    # 8. Red Flags Query
    res = client.post(
        f"/analysis/{analysis_id}/red-flags/query",
        json={"question": "What are the supply chain and trade risks?"}
    )
    print("8. Red Flags Query:", res.status_code)
    assert res.status_code == 200
    rf_query_data = res.json()
    print("   rf query answer snippet:", str(rf_query_data.get("answer"))[:100])
    assert rf_query_data.get("answer")

    # 9. Comparison before Company B (must be 404)
    res = client.get(f"/analysis/{analysis_id}/comparison")
    print("9. Comparison before Company B (expect 404):", res.status_code)
    assert res.status_code == 404

    # 10. Upload Company B (Nimbus Cloud)
    with open("nimbus_cloud.txt", "rb") as f:
        comp_bytes = f.read()

    res = client.post(
        f"/analysis/{analysis_id}/comparison/upload",
        files={"file": ("nimbus_cloud.txt", comp_bytes, "text/plain")},
        data={"company_name": "Nimbus Cloud", "report_year": "2024"}
    )
    print("10. Comparison Upload:", res.status_code)
    assert res.status_code == 200
    comp_upload_data = res.json()
    print("    companies compared:", comp_upload_data.get("companies"))
    assert len(comp_upload_data.get("companies", [])) == 2

    # 11. Comparison Result
    res = client.get(f"/analysis/{analysis_id}/comparison")
    print("11. Comparison Result:", res.status_code)
    assert res.status_code == 200
    comp_data = res.json()
    print("    records count:", len(comp_data.get("records", [])))
    assert len(comp_data.get("records", [])) > 0

    # 12. Report JSON
    res = client.get(f"/analysis/{analysis_id}/report")
    print("12. Report JSON:", res.status_code)
    assert res.status_code == 200
    report_data = res.json()
    print("    executive_summary snippet:", str(report_data.get("executive_summary"))[:100])
    print("    report_status:", report_data.get("report_status"))
    assert report_data.get("executive_summary")

    # 13. PDF Download
    res = client.get(f"/analysis/{analysis_id}/report/download")
    print("13. PDF Download:", res.status_code, "Content-Type:", res.headers.get("content-type"), "Length:", len(res.content))
    assert res.status_code == 200
    assert res.headers.get("content-type") == "application/pdf"
    assert res.content.startswith(b"%PDF-"), "Downloaded file does not start with %PDF- header!"
    print("    VALID PDF HEADER DETECTED (%PDF-)")

    # 14. Error handling tests
    # Invalid extension
    bad_res = client.post(
        "/analysis/upload",
        files={"file": ("bad.exe", b"invalid", "application/octet-stream")}
    )
    print("14. Bad extension (expect 400):", bad_res.status_code)
    assert bad_res.status_code == 400

    # Non-existent session
    non_res = client.get("/analysis/nonexistent-session-id/status")
    print("15. Nonexistent session (expect 404):", non_res.status_code)
    assert non_res.status_code == 404

    print("\nALL 15 REAL BACKEND API CONTRACT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_full_pipeline()
