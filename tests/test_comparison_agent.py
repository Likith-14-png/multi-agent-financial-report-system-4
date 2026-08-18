import json

from compare import compare_company_metrics, compare_report_metrics


def test_compare_extracted_metrics_single_year_snapshot():
    extracted = {
        "analysis_id": "analysis-1",
        "document_id": "doc-1",
        "company_name": "ABB",
        "report_year": 2025,
        "chunk_id": "chunk-1",
        "revenue": "$15.3 billion",
        "operating_income": "$2.1 billion",
        "net_income": "$1.2 billion",
    }

    result = compare_report_metrics(extracted)

    assert result["metadata"]["company_name"] == "ABB"
    assert result["metadata"]["report_year"] == 2025
    assert any(r["metric"] == "Revenue" for r in result["records"])
    assert any(r["metric"] == "Operating Income" for r in result["records"])
    assert result["records"][0]["source_chunks"]


def test_compare_extracted_metrics_year_over_year_increase():
    extracted = {
        "company_name": "ABB",
        "report_year": 2025,
        "yearly_metrics": {
            "Revenue": [
                {"year": 2024, "value": "14.0 billion"},
                {"year": 2025, "value": "15.3 billion"},
            ]
        },
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert str(revenue["previous_year"]) == "2024"
    assert str(revenue["current_year"]) == "2025"
    assert revenue["current_value"] == 15.3
    assert revenue["absolute_change"] == 1.3
    assert revenue["direction"] == "increase"
    assert revenue["percentage_change"] > 0


def test_compare_extracted_metrics_year_over_year_decrease():
    extracted = {
        "company_name": "ABB",
        "report_year": 2025,
        "yearly_metrics": {
            "Revenue": [
                {"year": 2024, "value": "16.0 billion"},
                {"year": 2025, "value": "14.5 billion"},
            ]
        },
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert revenue["direction"] == "decrease"
    assert revenue["absolute_change"] == -1.5


def test_compare_report_metrics_prefers_report_year_when_series_is_stale():
    extracted = {
        "company_name": "Orion Digital Infrastructure Ltd.",
        "report_year": 2026,
        "yearly_metrics": {
            "Revenue": [
                {"year": 2024, "value": "16.35 billion"},
                {"year": 2025, "value": "18.4 billion"},
            ]
        },
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert str(revenue["current_year"]) == "2026"
    assert str(revenue["previous_year"]) == "2025"


def test_compare_extracted_metrics_zero_previous_value_is_safe():
    extracted = {
        "company_name": "ABB",
        "report_year": 2025,
        "yearly_metrics": {
            "Revenue": [
                {"year": 2024, "value": "0"},
                {"year": 2025, "value": "5.0 billion"},
            ]
        },
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert revenue["direction"] == "increase"
    assert revenue["percentage_change"] is None


def test_compare_ignores_filename_entries_in_source_chunks():
    extracted = {
        "company_name": "ABB",
        "report_year": 2026,
        "source": "mock_financial_report_2025_2026.pdf",
        "source_chunks": ["chunk-1", "mock_financial_report_2025_2026.pdf", "chunk-1"],
        "yearly_metrics": {
            "Revenue": [
                {"year": 2025, "value": "15.3 billion"},
                {"year": 2026, "value": "16.1 billion"},
            ]
        },
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert "chunk-1" in revenue["source_chunks"]
    assert not any(".pdf" in chunk for chunk in revenue["source_chunks"])


def test_compare_preserves_legitimate_multiple_source_chunks_and_excludes_stale_metadata():
    extracted = {
        "company_name": "Orion Digital Infrastructure Ltd.",
        "report_year": 2026,
        "source": "shared_report_metadata_2026.txt",
        "source_chunks": ["stale_shared_chunk", "chunk-current-2026"],
        "yearly_metrics": {
            "Revenue": [
                {"year": 2025, "value": "15.3 billion", "source_chunks": ["chunk-2025-fy25", "chunk-2025-fy25"], "chunk_id": "chunk-2025-fy25"},
                {"year": 2026, "value": "16.1 billion", "source_chunks": ["chunk-current-2026", "chunk-current-2026"], "chunk_id": "chunk-current-2026"},
            ]
        },
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert revenue["source_chunks"] == ["chunk-2025-fy25", "chunk-current-2026"]
    assert "stale_shared_chunk" not in revenue["source_chunks"]
    assert "shared_report_metadata_2026.txt" not in revenue["source_chunks"]
    assert not any(chunk.startswith("shared_") for chunk in revenue["source_chunks"])


def test_compare_company_metrics_supports_cross_company_values():
    result = compare_company_metrics(
        {"company_name": "ABB", "metric": "Revenue", "value": "15.3 billion"},
        {"company_name": "Beta", "metric": "Revenue", "value": "18.2 billion"},
    )

    assert result["metric"] == "Revenue"
    assert result["company_a"]["company_name"] == "ABB"
    assert result["company_b"]["company_name"] == "Beta"
    assert result["difference"] == 2.9


def test_compare_report_metrics_serializes_to_json():
    extracted = {
        "analysis_id": "analysis-1",
        "document_id": "doc-1",
        "company_name": "ABB",
        "report_year": 2025,
        "chunk_id": "chunk-1",
        "revenue": "$15.3 billion",
        "total_assets": "$10.0 billion",
    }

    result = compare_report_metrics(extracted)
    payload = json.dumps(result)

    assert "Revenue" in payload
    assert "Total Assets" in payload
    assert "ABB" in payload
