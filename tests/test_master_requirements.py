import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction-agent"))

from compare import compare_company_metrics
from extraction_agent import extract_report_metrics
from app.services.offline_analyzer import OfflineAnalyzer


def test_extraction_preserves_canonical_value_and_material_weakness_negation():
    result = extract_report_metrics(
        "No material weakness was identified. Revenue was $520 million. Operating margin was 19.0%.",
        metadata={"company_name": "TCS", "report_year": "2024", "currency": "USD"},
        enable_llm=False,
    )

    assert result["material_weakness"]["status"] == "none_identified"
    assert result["financial_values"]["revenue"]["value"] == 520.0
    assert result["financial_values"]["revenue"]["display_value"] == "$520 million"
    assert result["financial_values"]["operating_margin"]["unit_scale"] == "percent"


def test_reported_nil_is_zero_and_not_missing():
    result = extract_report_metrics("Total debt: NIL.", metadata={"company_name": "TCS", "report_year": "2024"}, enable_llm=False)
    assert result["total_debt"] == "NIL"
    assert result["financial_values"]["total_debt"]["value"] == 0.0
    assert result["financial_values"]["total_debt"]["status"] == "reported_zero"


def test_comparison_rejects_currency_mismatch_without_conversion():
    result = compare_company_metrics(
        {"company_name": "TCS", "value": "₹267,021 crore", "currency": "INR"},
        {"company_name": "Apex", "value": "$520 million", "currency": "USD"},
        metric_name="Revenue",
    )
    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None


def test_comparison_rejects_non_equivalent_metric_names():
    result = compare_company_metrics(
        {"company_name": "TCS", "metric": "Revenue", "value": "₹267,021 crore", "currency": "INR", "document_id": "doc-a"},
        {"company_name": "Apex", "metric": "Net Income", "value": "$520 million", "currency": "USD", "document_id": "doc-b"},
    )
    assert result["comparison_status"] == "not_comparable"
    assert result["difference"] is None


@pytest.mark.parametrize(
    "current_value, previous_value, expected_status, expected_difference, expected_percentage, expected_direction",
    [
        (250, 200, "comparable", 50.0, 25.0, "increase"),
        (200, 250, "comparable", -50.0, -20.0, "decrease"),
        (200, 200, "equal", 0.0, 0.0, "unchanged"),
        (5, 0, "comparable", 5.0, None, "increase"),
    ],
)
def test_comparison_uses_period_order_for_current_and_previous(current_value, previous_value, expected_status, expected_difference, expected_percentage, expected_direction):
    current_year = 2025
    previous_year = 2024
    result = compare_company_metrics(
        {"company_name": "CurrentCo", "metric": "Revenue", "value": current_value, "currency": "USD", "unit": "million", "report_year": current_year},
        {"company_name": "PriorCo", "metric": "Revenue", "value": previous_value, "currency": "USD", "unit": "million", "report_year": previous_year},
        metric_name="Revenue",
    )
    assert result["comparison_status"] == expected_status
    assert result["difference"] == expected_difference
    assert result["percentage_difference"] == expected_percentage
    assert result["direction"] == expected_direction


def test_comparison_normalizes_same_currency_indian_scales():
    result = compare_company_metrics(
        {"company_name": "A", "value": "₹2 crore", "currency": "INR"},
        {"company_name": "B", "value": "₹20 million", "currency": "INR"},
        metric_name="Revenue",
    )
    assert result["comparison_status"] == "equal"
    assert result["difference"] == 0.0


def test_offline_analyzer_does_not_flag_unrelated_decline():
    result = OfflineAnalyzer().analyze("PPA decline was disclosed; revenue remained stable.", [{"document": "PPA decline was disclosed; revenue remained stable."}])
    assert not any(flag["category"] == "performance" for flag in result["flags"])