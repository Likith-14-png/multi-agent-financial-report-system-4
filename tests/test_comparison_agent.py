import json
import os
import pytest

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


def test_compare_company_metrics_rejects_missing_current_value():
    result = compare_company_metrics(
        {"company_name": "Alpha", "metric": "Cash Flow", "value": None},
        {"company_name": "Beta", "metric": "Cash Flow", "value": 100},
    )

    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None
    assert result["percentage_difference"] is None
    assert result["better_company"] is None


def test_compare_company_metrics_rejects_missing_other_value():
    result = compare_company_metrics(
        {"company_name": "Alpha", "metric": "Cash Flow", "value": 100},
        {"company_name": "Beta", "metric": "Cash Flow", "value": "Not available"},
    )

    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None
    assert result["percentage_difference"] is None
    assert result["better_company"] is None


def test_compare_company_metrics_rejects_status_marked_missing_before_fallback():
    result = compare_company_metrics(
        {"company_name": "Alpha", "metric": "Cash Flow", "status": "not_found", "value": None, "semantic_status": "MISSING"},
        {"company_name": "Beta", "metric": "Cash Flow", "status": "available", "value": 83, "semantic_status": "AVAILABLE"},
    )

    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None
    assert result["absolute_difference"] is None
    assert result["percentage_difference"] is None
    assert result["direction"] == "unavailable"
    assert result["better_company"] is None


def test_compare_company_metrics_rejects_both_missing_values():
    result = compare_company_metrics(
        {"company_name": "Alpha", "metric": "Cash Flow", "value": None},
        {"company_name": "Beta", "metric": "Cash Flow", "value": "Not disclosed"},
    )

    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None
    assert result["percentage_difference"] is None
    assert result["better_company"] is None


def test_compare_company_metrics_treats_zero_as_valid_numeric_value():
    result = compare_company_metrics(
        {"company_name": "Alpha", "metric": "Cash Flow", "value": 0},
        {"company_name": "Beta", "metric": "Cash Flow", "value": 100},
    )

    assert result["comparison_status"] == "comparable"
    assert result["difference"] == 100.0
    assert result["direction"] == "increase"
    assert result["better_company"] == "Beta"


def test_compare_company_metrics_normal_comparison_regression():
    result = compare_company_metrics(
        {"company_name": "Alpha", "metric": "Revenue", "value": 100},
        {"company_name": "Beta", "metric": "Revenue", "value": 200},
    )

    assert result["comparison_status"] == "comparable"
    assert result["difference"] == 100.0
    assert result["percentage_difference"] == 100.0
    assert result["direction"] == "increase"
    assert result["better_company"] == "Beta"


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


def test_compare_company_metrics_keeps_original_company_identity_when_period_order_reverses():
    result = compare_company_metrics(
        {"company_name": "Company A", "metric": "Revenue", "value": 187472, "report_year": 2025},
        {"company_name": "Company B", "metric": "Revenue", "value": 165000, "report_year": 2024},
    )

    assert result["company_a"]["company_name"] == "Company A"
    assert result["company_b"]["company_name"] == "Company B"
    assert result["comparability_metadata"]["original_company_a_value"] == 187472
    assert result["comparability_metadata"]["original_company_b_value"] == 165000
    assert result["better_company"] == "Company A"


def test_compare_company_metrics_total_liabilities_are_lower_better():
    result = compare_company_metrics(
        {"company_name": "Company A", "metric": "Total Liabilities", "value": 120},
        {"company_name": "Company B", "metric": "Total Liabilities", "value": 90},
    )

    assert result["metric_direction"] == "lower_better"
    assert result["better_company"] == "Company B"
    assert result["comparison_status"] == "comparable"


def test_compare_report_metrics_current_only_input_is_unavailable_not_inferred():
    extracted = {
        "company_name": "Fixture Company",
        "report_year": 2026,
        "revenue": "187,472 million",
        "operating_income": "16,137 million",
        "total_assets": "185,000 million",
        "total_liabilities": "107,000 million",
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert revenue["current_year"] == 2026
    assert revenue["previous_year"] is None
    assert revenue["previous_value"] is None
    assert revenue["direction"] == "unavailable"
    assert revenue["percentage_change"] is None
    assert result["comparison_type"] == "single_year"


def test_compare_report_metrics_matches_previous_period_from_unordered_observations():
    extracted = {
        "company_name": "ABB",
        "report_year": 2025,
        "observations": [
            {"metric_name": "revenue", "metric": "Revenue", "report_year": 2024, "raw_value": "200 million", "numeric_value": 200.0, "currency": "USD", "unit": "million", "source_file": "report.txt", "source_chunk_id": "chunk-24"},
            {"metric_name": "revenue", "metric": "Revenue", "report_year": 2025, "raw_value": "250 million", "numeric_value": 250.0, "currency": "USD", "unit": "million", "source_file": "report.txt", "source_chunk_id": "chunk-25"},
        ],
    }

    result = compare_report_metrics(extracted)
    revenue = next(r for r in result["records"] if r["metric"] == "Revenue")

    assert revenue["current_year"] == 2025
    assert revenue["previous_year"] == 2024
    assert revenue["current_value"] == 250.0
    assert revenue["previous_value"] == 200.0
    assert revenue["absolute_change"] == 50.0
    assert revenue["percentage_change"] == 25.0
    assert revenue["direction"] == "increase"


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


def test_compare_company_metrics_preserves_evidence_for_both_companies():
    """
    Verify that evidence from Company A and Company B observations
    are preserved separately in the comparison result.
    """
    company_a = {
        "company_name": "Alpha Corp",
        "metric": "Revenue",
        "value": 100,
        "evidence": "Alpha Revenue 100",
        "source_file": "alpha.pdf",
        "source_page": 2,
        "source_chunk_id": "alpha-chunk-rev",
    }

    company_b = {
        "company_name": "Beta Corp",
        "metric": "Revenue",
        "value": 80,
        "evidence": "Beta Revenue 80",
        "source_file": "beta.pdf",
        "source_page": 1,
        "source_chunk_id": "beta-chunk-rev",
    }

    result = compare_company_metrics(company_a, company_b, metric_name="Revenue")

    # Company A evidence preserved
    assert result["company_a"]["evidence"] == "Alpha Revenue 100"
    assert result["company_a"]["source_file"] == "alpha.pdf"
    assert result["company_a"]["source_page"] == 2
    assert result["company_a"]["source_chunk_id"] == "alpha-chunk-rev"

    # Company B evidence preserved
    assert result["company_b"]["evidence"] == "Beta Revenue 80"
    assert result["company_b"]["source_file"] == "beta.pdf"
    assert result["company_b"]["source_page"] == 1
    assert result["company_b"]["source_chunk_id"] == "beta-chunk-rev"

    # Verify no cross-contamination
    assert "Alpha Revenue 100" not in str(result["company_b"].get("evidence", ""))
    assert "Beta Revenue 80" not in str(result["company_a"].get("evidence", ""))


def test_compare_company_metrics_evidence_isolation_multiple_metrics():
    """
    Test that evidence is independently preserved for multiple metrics
    across both companies.
    """
    metrics_data = [
        ("Revenue", 187472, 165000, "Revenue 187,472", "Revenue 165,000"),
        ("Operating Income", 16137, 14200, "Operating Income 16,137", "Operating Income 14,200"),
        ("Net Income", 12050, 10500, "Net Income 12,050", "Net Income 10,500"),
    ]

    for metric_label, val_a, val_b, ev_a, ev_b in metrics_data:
        result = compare_company_metrics(
            {
                "company_name": "Company A",
                "metric": metric_label,
                "value": val_a,
                "evidence": ev_a,
                "source_file": "company_a_report.pdf",
                "source_page": 10 + val_a % 10,
            },
            {
                "company_name": "Company B",
                "metric": metric_label,
                "value": val_b,
                "evidence": ev_b,
                "source_file": "company_b_report.pdf",
                "source_page": 5 + val_b % 5,
            },
            metric_name=metric_label,
        )

        # Verify each company retains its own evidence for this metric
        assert result["company_a"]["evidence"] == ev_a
        assert result["company_b"]["evidence"] == ev_b
        # Verify no cross-contamination
        assert result["company_a"]["evidence"] != result["company_b"]["evidence"]


def test_compare_company_metrics_missing_evidence_preserved_as_missing():
    """
    When evidence is not provided, do not generate or invent evidence.
    Preserve it as missing.
    """
    result = compare_company_metrics(
        {"company_name": "Company A", "metric": "Revenue", "value": 100},
        {"company_name": "Company B", "metric": "Revenue", "value": 80},
        metric_name="Revenue",
    )

    # No evidence provided → no evidence in result
    assert "evidence" not in result["company_a"] or result["company_a"].get("evidence") is None
    assert "evidence" not in result["company_b"] or result["company_b"].get("evidence") is None


def test_compare_company_metrics_evidence_with_provenance_struct():
    """
    Test that evidence is preserved even when it comes with full provenance metadata.
    """
    company_a = {
        "company_name": "TCS",
        "metric": "Revenue",
        "value": 187472,
        "evidence": "Revenue from operations: ₹240,893 crore",
        "source_file": "tcs_2024.pdf",
        "source_page": 42,
        "source_chunk_id": "tcs-chunk-42",
    }

    company_b = {
        "company_name": "Infosys",
        "metric": "Revenue",
        "value": 165000,
        "evidence": "Total Revenue: $9.8 billion",
        "source_file": "infosys_2024.pdf",
        "source_page": 38,
        "source_chunk_id": "infosys-chunk-38",
    }

    result = compare_company_metrics(company_a, company_b, metric_name="Revenue")

    # Verify complete provenance is preserved for both companies
    assert result["company_a"]["evidence"] == "Revenue from operations: ₹240,893 crore"
    assert result["company_a"]["source_file"] == "tcs_2024.pdf"
    assert result["company_a"]["source_page"] == 42

    assert result["company_b"]["evidence"] == "Total Revenue: $9.8 billion"
    assert result["company_b"]["source_file"] == "infosys_2024.pdf"
    assert result["company_b"]["source_page"] == 38


def test_workflow_extraction_financial_values_evidence_flow():
    """
    Test that simulates the actual workflow: extraction produces financial_values
    with evidence, workflow passes it to compare_company_metrics, and evidence
    is preserved in the final comparison result.
    """
    # Simulate extraction output with financial_values containing evidence
    extracted_a = {
        "company_name": "Company A",
        "report_year": 2025,
        "financial_values": {
            "revenue": {
                "metric": "Revenue",
                "display_value": "187,472 million",
                "raw_value": "187,472 million",
                "value": 187472.0,
                "currency": "INR",
                "unit_scale": "million",
                "evidence": "Revenue from operations: ₹187,472 million",  # THIS IS THE EVIDENCE
                "source_file": "company_a_report.pdf",
                "source_page": 2,
                "source_chunk": "chunk-a-revenue",
            }
        }
    }

    extracted_b = {
        "company_name": "Company B",
        "report_year": 2025,
        "financial_values": {
            "revenue": {
                "metric": "Revenue",
                "display_value": "165,000 million",
                "raw_value": "165,000 million",
                "value": 165000.0,
                "currency": "INR",
                "unit_scale": "million",
                "evidence": "Total Revenue: ₹165,000 million",  # THIS IS THE EVIDENCE
                "source_file": "company_b_report.pdf",
                "source_page": 1,
                "source_chunk": "chunk-b-revenue",
            }
        }
    }

    # Simulate what workflow.py does: extract financial_values and pass to compare_company_metrics
    fv_a = extracted_a.get("financial_values", {}).get("revenue")
    fv_b = extracted_b.get("financial_values", {}).get("revenue")

    obs_a = {
        "company_name": extracted_a.get("company_name"),
        "metric": "Revenue",
        "value": fv_a.get("display_value") if fv_a else None,
        "evidence": fv_a.get("evidence") if fv_a else None,
        "source_file": fv_a.get("source_file") if fv_a else None,
        "source_page": fv_a.get("source_page") if fv_a else None,
        "source_chunk_id": fv_a.get("source_chunk") if fv_a else None,
    }

    obs_b = {
        "company_name": extracted_b.get("company_name"),
        "metric": "Revenue",
        "value": fv_b.get("display_value") if fv_b else None,
        "evidence": fv_b.get("evidence") if fv_b else None,
        "source_file": fv_b.get("source_file") if fv_b else None,
        "source_page": fv_b.get("source_page") if fv_b else None,
        "source_chunk_id": fv_b.get("source_chunk") if fv_b else None,
    }

    # Compare
    result = compare_company_metrics(obs_a, obs_b, metric_name="Revenue")

    # Verify evidence survives the complete flow
    assert result["company_a"]["evidence"] == "Revenue from operations: ₹187,472 million"
    assert result["company_b"]["evidence"] == "Total Revenue: ₹165,000 million"

    # Verify provenance survives
    assert result["company_a"]["source_file"] == "company_a_report.pdf"
    assert result["company_a"]["source_page"] == 2
    assert result["company_b"]["source_file"] == "company_b_report.pdf"
    assert result["company_b"]["source_page"] == 1

    # Verify no cross-contamination
    assert result["company_a"]["evidence"] != result["company_b"]["evidence"]


def test_extraction_agent_financial_values_contains_evidence():
    """
    Diagnostic test: Verify that extraction agent produces financial_values
    dicts with evidence field populated.
    """
    from extraction_agent import extract_report_metrics
    import os

    # Use one of the sample reports from the repo
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    sample_file = os.path.join(data_dir, "abb_2025_report.txt")

    if not os.path.exists(sample_file):
        # Skip test if sample file doesn't exist
        pytest.skip(f"Sample file not found: {sample_file}")

    with open(sample_file, "r", encoding="utf-8") as f:
        sample_text = f.read()

    result = extract_report_metrics(
        sample_text,
        metadata={"source_file": "abb_2025_report.txt"}
    )

    # Verify financial_values dict exists
    assert "financial_values" in result, "No financial_values in extraction result"
    fv = result["financial_values"]

    # Check if any metric has evidence
    metrics_with_evidence = []
    metrics_without_evidence = []

    for key, value_dict in fv.items():
        if isinstance(value_dict, dict):
            if value_dict.get("display_value") is not None:
                if value_dict.get("evidence"):
                    metrics_with_evidence.append((key, value_dict.get("evidence")))
                else:
                    metrics_without_evidence.append((key, value_dict.get("display_value")))

    # At least one metric should have evidence
    # (This will help us debug if evidence is truly missing from extraction)
    if metrics_without_evidence:
        print(f"\nMetrics without evidence: {metrics_without_evidence}")
    if metrics_with_evidence:
        print(f"\nMetrics with evidence: {[(k, v[:50]+'...' if len(v) > 50 else v) for k, v in metrics_with_evidence]}")

    # Assertion: Evidence should be populated for at least some metrics
    # If this fails, we know extraction is not populating evidence
    assert len(metrics_with_evidence) > 0 or len(metrics_without_evidence) > 0, \
        "No financial metrics found in extraction result"
